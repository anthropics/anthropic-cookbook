import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import (
    dataclass,
    field,
)

import aiohttp
from anthropic import Anthropic
from loguru import logger


async def process_api_requests_from_file(
    requests_filepath: str,
    save_filepath: str,
    request_url: str,
    use_caching: bool,
    api_key: str,
    max_requests_per_minute: float,
    max_tokens_per_minute: float,
    max_attempts: int,
):
    """Processes API requests in parallel, throttling to stay under rate limits."""
    client = Anthropic(api_key=api_key)

    # constants
    seconds_to_pause_after_rate_limit_error = 15
    seconds_to_sleep_each_loop = (
        0.001  # 1 ms limits max throughput to 1,000 requests per second
    )

    # infer API endpoint and construct request header
    request_header = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if use_caching:
        request_header["anthropic-beta"] = "prompt-caching-2024-07-31"

    queue_of_requests_to_retry = asyncio.Queue()
    task_id_generator = task_id_generator_function()
    status_tracker = StatusTracker(
        available_token_capacity=max_tokens_per_minute, use_caching=use_caching
    )
    next_request = None

    available_request_capacity = max_requests_per_minute

    last_update_time = time.time()

    # initialize flags
    file_not_finished = True  # after file is empty, we'll skip reading it
    logger.debug("Initialization complete.")

    def create_api_request(request_json):
        """Helper function: Create an APIRequest object from a request JSON."""
        next_request = APIRequest(
            task_id=next(task_id_generator),
            request_json=request_json,
            estimate_token_consumption=estimate_num_tokens_from_request(
                client,
                request_json,
                use_caching,
                status_tracker.caching_status,
            ),
            attempts_left=max_attempts,
            metadata=request_json.pop("metadata", None),
        )
        status_tracker.num_tasks_started += 1
        status_tracker.num_tasks_in_progress += 1
        logger.debug(f"Reading request {next_request.task_id}: {next_request}")
        return next_request

    with open(requests_filepath) as file:
        requests = file.__iter__()
        logger.debug("File opened. Entering main loop")
        async with aiohttp.ClientSession() as session:

            if use_caching:
                logger.info("Initiating caching")
                request_json = json.loads(next(requests))
                next_request = create_api_request(request_json)

                await next_request.call_api(
                    session=session,
                    request_url=request_url,
                    request_header=request_header,
                    retry_queue=queue_of_requests_to_retry,
                    save_filepath=save_filepath,
                    status_tracker=status_tracker,
                )
                next_request = None

                if status_tracker.caching_status:
                    logger.success("Caching is enabled and working.")
                else:
                    logger.warning(
                        "Failed to enable caching. Processing without caching in 10s."
                    )
                    time.sleep(10)

            while True:
                # get next request (if one is not already waiting for capacity)
                if next_request is None:
                    if not queue_of_requests_to_retry.empty():
                        next_request = queue_of_requests_to_retry.get_nowait()
                        logger.debug(
                            f"Retrying request {next_request.task_id}: {next_request}"
                        )
                    elif file_not_finished:
                        try:
                            # get new request
                            request_json = json.loads(next(requests))
                            next_request = create_api_request(request_json)

                        except StopIteration:
                            # if file runs out, set flag to stop reading it
                            logger.debug("Read file exhausted")
                            file_not_finished = False

                # update available capacity
                current_time = time.time()
                seconds_since_update = current_time - last_update_time
                available_request_capacity = min(
                    available_request_capacity
                    + max_requests_per_minute * seconds_since_update / 60.0,
                    max_requests_per_minute,
                )
                status_tracker.available_token_capacity = min(
                    status_tracker.available_token_capacity
                    + max_tokens_per_minute * seconds_since_update / 60.0,
                    max_tokens_per_minute,
                )
                last_update_time = current_time

                # if enough capacity available, call API
                if next_request:
                    next_request_tokens = next_request.estimate_token_consumption
                    if (
                        available_request_capacity >= 1
                        and status_tracker.available_token_capacity
                        >= next_request_tokens
                    ):
                        # update counters
                        available_request_capacity -= 1
                        status_tracker.available_token_capacity -= next_request_tokens
                        next_request.attempts_left -= 1

                        # call API
                        asyncio.create_task(
                            next_request.call_api(
                                session=session,
                                request_url=request_url,
                                request_header=request_header,
                                retry_queue=queue_of_requests_to_retry,
                                save_filepath=save_filepath,
                                status_tracker=status_tracker,
                            )
                        )

                        next_request = None

                # if all tasks are finished, break
                if status_tracker.num_tasks_in_progress == 0:
                    break

                # main loop sleeps briefly so concurrent tasks can run
                await asyncio.sleep(seconds_to_sleep_each_loop)

                # if a rate limit error was hit recently, pause to cool down
                seconds_since_rate_limit_error = (
                    time.time() - status_tracker.time_of_last_rate_limit_error
                )
                if (
                    seconds_since_rate_limit_error
                    < seconds_to_pause_after_rate_limit_error
                ):
                    remaining_seconds_to_pause = (
                        seconds_to_pause_after_rate_limit_error
                        - seconds_since_rate_limit_error
                    )
                    await asyncio.sleep(remaining_seconds_to_pause)
                    logger.warning(
                        f"Pausing to cool down until {time.ctime(status_tracker.time_of_last_rate_limit_error + seconds_to_pause_after_rate_limit_error)}"
                    )

        # after finishing, log final status
        logger.info(
            f"""Parallel processing complete. Results saved to {save_filepath}"""
        )
        logger.info(f"""Total input tokens {status_tracker.total_tokens_used}""")

        if status_tracker.num_tasks_failed > 0:
            logger.warning(
                f"{status_tracker.num_tasks_failed} / {status_tracker.num_tasks_started} requests failed. Errors logged to {save_filepath}."
            )
        if status_tracker.num_rate_limit_errors > 0:
            logger.warning(
                f"{status_tracker.num_rate_limit_errors} rate limit errors received. Consider running at a lower rate."
            )


@dataclass
class StatusTracker:
    """Stores metadata about the script's progress. Only one instance is created."""

    num_tasks_started: int = 0
    num_tasks_in_progress: int = 0  # script ends when this reaches 0
    num_tasks_succeeded: int = 0
    num_tasks_failed: int = 0
    num_rate_limit_errors: int = 0
    num_api_errors: int = 0  # excluding rate limit errors, counted above
    num_other_errors: int = 0
    time_of_last_rate_limit_error: int = 0  # used to cool off after hitting rate limits
    total_tokens_used: int = 0
    available_token_capacity: int = 0
    use_caching: bool = False
    caching_status: bool = False


@dataclass
class APIRequest:
    """Stores an API request's inputs, outputs, and other metadata. Contains a method to make an API call."""

    task_id: int
    request_json: dict
    estimate_token_consumption: int
    attempts_left: int
    metadata: dict
    result: list = field(default_factory=list)

    async def call_api(
        self,
        session: aiohttp.ClientSession,
        request_url: str,
        request_header: dict,
        retry_queue: asyncio.Queue,
        save_filepath: str,
        status_tracker: StatusTracker,
    ):
        """Calls the Anthropic API and saves results."""
        logger.info(f"Starting request #{self.task_id}")
        error = None
        try:
            async with session.post(
                url=request_url, headers=request_header, json=self.request_json
            ) as response:
                response_json = await response.json()

            if response.status == 200:
                # Successful API call
                self.actual_tokens = response_json.get("usage", {}).get(
                    "input_tokens", 0
                )
                if status_tracker.use_caching:
                    num_cache_read_tokens = response_json.get("usage", {}).get(
                        "cache_read_input_tokens", 0
                    )
                    num_cache_creation_tokens = response_json.get("usage", {}).get(
                        "cache_creation_input_tokens", 0
                    )
                    if num_cache_read_tokens > 0 or num_cache_creation_tokens > 0:
                        status_tracker.caching_status = True
                    else:
                        status_tracker.caching_status = False

                # Update token usage
                update_token_usage(self, status_tracker)
                status_tracker.total_tokens_used += self.actual_tokens

                data = (
                    [self.request_json, response_json, self.metadata]
                    if self.metadata
                    else [self.request_json, response_json]
                )
                append_to_jsonl(data, save_filepath)
                status_tracker.num_tasks_succeeded += 1
                logger.debug(
                    f"Request {self.task_id} completed. Tokens used: {self.actual_tokens}"
                )

            else:
                # Handle error cases
                error = response_json.get("error", str(response_json))
                status_tracker.num_api_errors += 1
                if "rate limit" in str(error).lower():
                    status_tracker.time_of_last_rate_limit_error = time.time()
                    status_tracker.num_rate_limit_errors += 1
                    status_tracker.num_api_errors -= 1

        except Exception as e:
            error = str(e)
            status_tracker.num_other_errors += 1

        if error:
            self.result.append(error)
            if self.attempts_left:
                retry_queue.put_nowait(self)
            else:
                logger.error(
                    f"Request {self.task_id} failed after all attempts. Error: {error}"
                )

                data = (
                    [self.request_json, [str(e) for e in self.result], self.metadata]
                    if self.metadata
                    else [self.request_json, [str(e) for e in self.result]]
                )
                append_to_jsonl(data, save_filepath)
                status_tracker.num_tasks_failed += 1

        status_tracker.num_tasks_in_progress -= 1

    def __str__(self):
        truncated_request = self.request_json.copy()
        if "system" in truncated_request:
            truncated_request["system"] = self.truncate_nested_dict(
                truncated_request["system"]
            )
        if "messages" in truncated_request:
            truncated_request["messages"] = self.truncate_nested_dict(
                truncated_request["messages"]
            )

        return (
            f"APIRequest(task_id={self.task_id}, "
            f"estimate_token_consumption={self.estimate_token_consumption}, "
            f"attempts_left={self.attempts_left}, "
            f"request_json={truncated_request})"
        )

    def truncate_nested_dict(self, prompt_part: list, max_length: int = 200) -> dict:
        """Truncate strings in a nested dictionary."""
        truncated = []
        for element in prompt_part:
            temp = {}
            for key, value in element.items():
                temp[key] = (
                    (value[:max_length] + "...") if len(value) > max_length else value
                )
            truncated.append(temp)
        return truncated


def append_to_jsonl(data, filename: str) -> None:
    """Append a json payload to the end of a jsonl file."""
    json_string = json.dumps(data)
    with open(filename, "a") as f:
        f.write(json_string + "\n")


def estimate_num_tokens_from_request(
    client: Anthropic, request_json: dict, use_caching: bool, caching_status: bool
) -> int:
    """
    Estimate the number of tokens consumed by a request.
    Returns an estimation of total tokens number.
    """
    # Count tokens in messages
    message_tokens = sum(
        client.count_tokens(message.get("content", ""))
        for message in request_json.get("messages", [])
    )

    # Count tokens in system messages
    system_tokens = 0
    cached_system_tokens = 0

    for element in request_json.get("system", []):
        text = element.get("text", "")
        token_count = client.count_tokens(text)

        if element.get("cache_control", {}).get("type") == "ephemeral":
            cached_system_tokens += token_count
        else:
            system_tokens += token_count

    # Determine total tokens based on caching settings
    if use_caching and caching_status:
        total_tokens = message_tokens + system_tokens
    else:
        total_tokens = message_tokens + system_tokens + cached_system_tokens

    return total_tokens


def update_token_usage(request: APIRequest, status_tracker: StatusTracker) -> None:
    """Update the token usage based on the actual tokens consumed by the request."""
    token_difference = request.actual_tokens - request.estimate_token_consumption
    new_capacity = status_tracker.available_token_capacity - token_difference

    if new_capacity < 0:
        logger.debug(
            f"Token capacity would have gone negative by {abs(new_capacity)} tokens. Resetting to 0."
        )
        status_tracker.available_token_capacity = 0
    else:
        status_tracker.available_token_capacity = new_capacity


def task_id_generator_function():
    """Generate integers 0, 1, 2, and so on."""
    task_id = 0
    while True:
        yield task_id
        task_id += 1


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--requests_filepath")
    parser.add_argument("--save_filepath", default=None)
    parser.add_argument(
        "--request_url", default="https://api.anthropic.com/v1/messages"
    )
    parser.add_argument("--use_caching", default=False)
    parser.add_argument("--api_key", default=os.getenv("ANTHROPIC_API_KEY"))
    parser.add_argument("--max_requests_per_minute", type=int, default=50 * 0.8)
    parser.add_argument("--max_tokens_per_minute", type=int, default=20_000 * 0.8)
    parser.add_argument("--max_attempts", type=int, default=5)
    parser.add_argument(
        "--logging_level",
        choices=["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    args = parser.parse_args()

    if args.save_filepath is None:
        args.save_filepath = args.requests_filepath.replace(".jsonl", "_results.jsonl")

    if args.logging_level:
        logger.remove()  # Remove the default handler
        logger.add(sys.stderr, level=args.logging_level)
        logger.debug(f"Logging initialized at level {args.logging_level}")

    # run script
    asyncio.run(
        process_api_requests_from_file(
            requests_filepath=args.requests_filepath,
            save_filepath=args.save_filepath,
            request_url=args.request_url,
            use_caching=args.use_caching,
            api_key=args.api_key,
            max_requests_per_minute=float(args.max_requests_per_minute),
            max_tokens_per_minute=float(args.max_tokens_per_minute),
            max_attempts=int(args.max_attempts),
        )
    )
