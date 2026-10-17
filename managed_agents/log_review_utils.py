"""Helpers for CMA_agent_security_review.ipynb.

The notebook holds the review itself: the rules, the selection, the four custom tools and the code that
answers them, the loop, the checks on each verdict, and the report's ranking. This module holds what the
notebook reads and shows with: exporting Managed Agents sessions, recording Messages API and Agent SDK
calls, converting all three log formats to one session record, validating the AGENTS entries, pulling hosts and
recipients out of a tool call's input, the cost estimate, the audit folder, and the tables the notebook
displays.
"""

import contextlib
import hashlib
import html
import ipaddress
import json
import os
import re
import stat
import textwrap
import time
import unicodedata
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import anthropic
import regex  # the third-party regex engine: same syntax as re, plus a per-search timeout

# --- Converting logs into session records -------------------------------------------------

MAX_RESULT_CHARS = 6000
# The depth from which a nested part of a log is replaced by a flat list of its values (see not_too_deep). An
# agent writes its own tool inputs, and the functions here that walk one call themselves, which Python stops at
# about a thousand levels. No honest input is nested even 64 deep.
MAX_DEPTH = 64


def text_of(blocks, depth=0):
    """Readable text of message content. A block that is not text (a fetched page, search results,
    code-execution output) is kept as JSON, and so is a result more than MAX_DEPTH results deep. In that JSON,
    whatever is nested MAX_DEPTH levels deep or deeper is a list of its values, without the names of their
    fields (see not_too_deep)."""
    if isinstance(blocks, str):
        return blocks
    if isinstance(blocks, dict):
        blocks = [blocks]
    parts = []
    for b in blocks or []:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b["text"])
        elif isinstance(b, dict) and b.get("type") == "tool_result" and depth < MAX_DEPTH:
            parts.append(text_of(b.get("content"), depth + 1))
        else:
            parts.append(json.dumps(not_too_deep(b)[0], ensure_ascii=False))
    return "\n".join(parts)


class RecordBuilder:
    def __init__(self, header):
        self.header, self.events, self.notes = header, [], []
        self.uncut = {}  # event number (as text) -> the whole text of a tool result that was cut

    def add(self, **ev):
        ev["i"] = len(self.events)
        self.events.append(ev)
        return ev

    def result(self, thread, call_id, content, is_error, source="tool_result"):
        text = text_of(content)
        ev = self.add(
            source=source,
            kind="tool_result",
            thread=thread,
            call_id=call_id,
            is_error=bool(is_error),
            content=text,
            elided_chars=0,
        )
        if len(text) > MAX_RESULT_CHARS:
            cut = len(text) - MAX_RESULT_CHARS
            half = MAX_RESULT_CHARS // 2
            ev["content"] = text[:half] + "\n[…]\n" + text[-half:]
            ev["elided_chars"] = cut
            self.uncut[str(ev["i"])] = text  # for the rules only: see record()
            self.notes.append(
                f"Tool output at event {ev['i']} cut: {cut:,} of {len(text):,} "
                "characters removed between head and tail."
            )

    def record(self):
        """The session record. "events" is what the reviewer is served and what a quote is checked against. "uncut"
        holds the whole text of each tool result that was cut, by event number, for the rules alone: they read it
        whole, and the cut text as well."""
        for note in self.notes:  # notes go last, so every other event keeps its index
            self.add(source="note", kind="elided", thread="main", content=note)
        record = {"session": self.header, "events": self.events}
        if self.uncut:
            record["uncut"] = self.uncut
        return record


def update_summary(event):
    """What a session.updated event changed: its fields are only those that changed."""
    changed = [k for k in ("agent", "budget", "metadata", "title") if event.get(k) is not None]
    summary = {"changed": changed}
    agent = event.get("agent") or {}
    for key in ("tools", "mcp_servers"):
        if key in agent:
            summary[key] = agent[key]
    return summary


def shape_error(where, exc):
    """The ValueError for a log the converter couldn't read: a missing field, or a shape it didn't expect."""
    if isinstance(exc, KeyError):
        return ValueError(f"{where}: missing field {exc}")
    return ValueError(f"{where}: unexpected shape here ({type(exc).__name__}: {exc})")


def normalize_managed_agents(export, deployment, first_message_is_task):
    """One Managed Agents session export (see export_session) -> session record. A missing field raises a
    ValueError that says which thread and event it was in."""
    ctx = {"where": "the top of the export (session, agent, threads)"}
    try:
        return _normalize_managed_agents(export, deployment, first_message_is_task, ctx)
    except (KeyError, TypeError, AttributeError) as exc:
        raise shape_error(ctx["where"], exc) from exc


def _normalize_managed_agents(export, deployment, first_message_is_task, ctx):
    ctx["where"] = "the session (id, created_at, updated_at) or the agent (name)"
    s, agent = export["session"], export["agent"]
    ctx["where"] = "the thread list (each thread needs id, parent_thread_id and events)"
    if not any(t["parent_thread_id"] is None for t in export["threads"]):
        raise ValueError(f"session {s['id']}: the export has no primary thread")
    ctx["where"] = "the session header (id, created_at, updated_at, agent name)"
    rb = RecordBuilder(
        {
            "id": s["id"],
            "log_source": "managed_agents",
            "agent": agent["name"],
            "agent_version": str(agent.get("version")),
            "deployment": deployment,
            "started_at": s["created_at"],
            "ended_at": s["updated_at"],
        }
    )
    rb.add(
        source="environment", kind="system_prompt", thread="main", content=agent.get("system") or ""
    )
    rb.add(
        source="environment", kind="tool_definitions", thread="main", content=agent.get("tools", [])
    )
    for k, thread in enumerate(export["threads"]):
        ctx["where"] = f"thread #{k} (it needs id, parent_thread_id, agent_name and events)"
        primary = thread["parent_thread_id"] is None
        name = "main" if primary else f"{thread['agent_name']} ({thread['id']})"
        ctx["where"] = f"thread {name}"
        seen_user = False
        for n, e in enumerate(thread["events"]):
            ctx["where"] = f"thread {name}, event {n}"
            t = e["type"]
            ctx["where"] += f" ({t})"
            if t == "user.message":
                if primary and not seen_user and first_message_is_task:
                    rb.add(
                        source="environment",
                        kind="task",
                        thread=name,
                        content=text_of(e["content"]),
                    )
                elif primary:
                    rb.add(
                        source="user", kind="message", thread=name, content=text_of(e["content"])
                    )
                else:  # a sub-agent's brief was written by the agent that started it
                    rb.add(source="agent", kind="brief", thread=name, content=text_of(e["content"]))
                seen_user = True
            elif t == "agent.message":
                rb.add(source="agent", kind="text", thread=name, content=text_of(e["content"]))
            elif t == "agent.thinking":  # the event carries no text; keep it so the reviewer knows
                rb.add(source="agent", kind="reasoning", thread=name, content=None)
            elif t in ("agent.tool_use", "agent.mcp_tool_use", "agent.custom_tool_use"):
                tool = (
                    f"{e['mcp_server_name']}/{e['name']}"
                    if t == "agent.mcp_tool_use"
                    else e["name"]
                )
                rb.add(
                    source="agent",
                    kind="tool_call",
                    thread=name,
                    tool=tool,
                    call_id=e["id"],
                    input=e.get("input", {}),
                )
                if e.get("evaluated_permission"):
                    evaluation = e.get("evaluation") or {}
                    judgement = evaluation.get("evaluated_permission") or {}
                    rb.add(
                        source="platform",
                        kind="permission",
                        thread=name,
                        call_id=e["id"],
                        decision=e["evaluated_permission"],
                        reason=judgement.get("reason_code"),
                        policy=evaluation.get("type"),
                    )
                elif t != "agent.custom_tool_use":
                    # An export carries null when no policy judged a built-in or MCP call. Custom tools are never
                    # judged by a policy, so they get no line.
                    rb.add(
                        source="platform",
                        kind="permission",
                        thread=name,
                        call_id=e["id"],
                        decision=None,
                        reason="no policy judged this call",
                        policy=None,
                    )
            elif t == "user.tool_confirmation":  # a person (or your code) answered an "ask"
                rb.add(
                    source="platform",
                    kind="confirmation",
                    thread=name,
                    call_id=e["tool_use_id"],
                    decision=e["result"],
                    content=e.get("deny_message"),
                )
            elif t == "system.message":  # developer-sent system context: it can steer the agent
                rb.add(
                    source="environment",
                    kind="system_message",
                    thread=name,
                    content=text_of(e["content"]),
                )
            elif (
                t == "session.updated"
            ):  # a change to the agent's tools, MCP servers or policies mid-session
                rb.add(
                    source="platform",
                    kind="session_updated",
                    thread=name,
                    content=update_summary(e),
                )
            elif t == "agent.thread_context_compacted":
                rb.add(
                    source="note",
                    kind="context_compacted",
                    thread=name,
                    content="The agent's context was compacted here: it no longer had the earlier events in view.",
                )
            elif t in (
                "agent.tool_result",
                "agent.mcp_tool_result",
                "user.custom_tool_result",
                "user.tool_result",
            ):
                call_id = (
                    e.get("tool_use_id") or e.get("mcp_tool_use_id") or e.get("custom_tool_use_id")
                )
                rb.result(name, call_id, e.get("content"), e.get("is_error"))
            elif t == "agent.thread_message_sent":
                rb.add(
                    source="agent",
                    kind="thread_message",
                    thread=name,
                    to=e.get("to_agent_name") or e["to_session_thread_id"],
                    content=text_of(e["content"]),
                )
            elif (
                t == "agent.thread_message_received"
            ):  # another agent's reply: material, not orders
                rb.add(
                    source="tool_result",
                    kind="thread_message",
                    thread=name,
                    sender=e.get("from_agent_name") or e["from_session_thread_id"],
                    content=text_of(e["content"]),
                )
            elif t == "user.interrupt":
                rb.add(source="user", kind="interrupt", thread=name, content=None)
            elif t == "session.error":
                rb.add(
                    source="platform",
                    kind="error",
                    thread=name,
                    content={"type": e["error"]["type"], "message": e["error"].get("message", "")},
                )
            elif t in ("session.status_idle", "session.thread_status_idle") and (
                (e.get("stop_reason") or {}).get("type") == "refusal"
            ):
                rb.add(
                    source="platform", kind="refusal", thread=name, content=e.get("stop_details")
                )
    return rb.record()


def normalize_messages_api(log, deployment, first_message_is_task):
    """One Messages API log ({"session_id", "agent", "exchanges": [{"request", "response"}]}) -> record.

    The last request holds the whole conversation. If an earlier request isn't a prefix of it (the
    agent's context was edited or compacted), a note tells the reviewer that turns may be missing. A block the
    converter doesn't show (an image, a document, a compaction block) leaves a note event saying so. A missing
    field raises a ValueError that says where in the log it was."""
    ctx = {"where": "the log header"}
    try:
        return _normalize_messages_api(log, deployment, first_message_is_task, ctx)
    except (KeyError, TypeError, AttributeError) as exc:
        raise shape_error(ctx["where"], exc) from exc


def _normalize_messages_api(log, deployment, first_message_is_task, ctx):
    last = log["exchanges"][-1]
    request, response = last["request"], last["response"]
    rb = RecordBuilder(
        {
            "id": log["session_id"],
            "log_source": "messages_api",
            "agent": log["agent"],
            "agent_version": "" if log.get("agent_version") is None else str(log["agent_version"]),
            "deployment": deployment,
            "started_at": log["started_at"],
            "ended_at": log["ended_at"],
        }
    )
    rb.add(
        source="environment",
        kind="system_prompt",
        thread="main",
        content=text_of(request.get("system") or ""),
    )
    rb.add(
        source="environment",
        kind="tool_definitions",
        thread="main",
        content=request.get("tools", []),
    )
    conversation = request["messages"] + [{"role": "assistant", "content": response["content"]}]
    for ex in log["exchanges"][:-1]:
        earlier = ex["request"]["messages"]
        if earlier != conversation[: len(earlier)]:
            rb.notes.append(
                "Earlier requests in this log don't match the final conversation; turns "
                "that were edited or compacted away are not in this record."
            )
            break
    for n, message in enumerate(conversation):
        blocks = message["content"]
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        for k, b in enumerate(blocks):
            ctx["where"] = f"message {n}, block {k}"
            kind = b["type"]
            if message["role"] == "user":
                if kind == "tool_result":
                    rb.result("main", b["tool_use_id"], b.get("content"), b.get("is_error"))
                elif kind == "text":
                    is_task = n == 0 and first_message_is_task
                    rb.add(
                        source="environment" if is_task else "user",
                        kind="task" if is_task else "message",
                        thread="main",
                        content=b["text"],
                    )
                else:
                    rb.add(
                        source="note",
                        kind="unshown_block",
                        thread="main",
                        content=f"A {kind} block isn't shown.",
                    )
            elif kind == "thinking":
                rb.add(
                    source="agent",
                    kind="reasoning",
                    thread="main",
                    content=b.get("thinking") or None,
                )
            elif kind == "redacted_thinking":
                rb.add(source="agent", kind="reasoning", thread="main", content=None)
            elif kind == "text":
                rb.add(source="agent", kind="text", thread="main", content=b["text"])
            elif kind in ("tool_use", "server_tool_use", "mcp_tool_use"):
                rb.add(
                    source="agent",
                    kind="tool_call",
                    thread="main",
                    tool=f"{b.get('server_name')}/{b['name']}"
                    if kind == "mcp_tool_use"
                    else b["name"],
                    call_id=b["id"],
                    input=b.get("input", {}),
                )
            elif kind.endswith(
                "_tool_result"
            ):  # results of server-side and MCP tools, such as web search
                rb.result("main", b.get("tool_use_id"), b.get("content"), b.get("is_error"))
            else:
                rb.add(
                    source="note",
                    kind="unshown_block",
                    thread="main",
                    content=f"A {kind} block isn't shown.",
                )
    for ex in log["exchanges"]:
        if ex["response"].get("stop_reason") == "refusal":
            rb.add(
                source="platform",
                kind="refusal",
                thread="main",
                content=ex["response"].get("stop_details"),
            )
    return rb.record()


# Agent SDK logs.
#
# The file is the one LoggedAgentSession writes: the options your code set, the prompts it sent, and each message
# the SDK gave it, in the SDK's wire shape. Four rules hold for every event that comes out:
#   1. Text is tagged environment or user only if the recorder wrote it down as set or sent by your own code (the
#      options and the prompts). Everything that arrived in the stream is agent, tool_result, platform or note.
#      What the runtime reported of itself in its first message (its tools, its permission mode, the names of its
#      sub-agents and MCP servers) is kept as short codes under a name of its own, "reported_by_the_runtime". It
#      never stands in for what your code set, and it never names a thread.
#   2. A platform event holds codes only: a fixed word, a value from the log that is a short code, or a call's id
#      that is a plain id. No sentence from the log is ever put in the platform's voice.
#   3. What the rest of this module indexes is always there: "decision" and "call_id" on a permission or a
#      confirmation, "call_id" (text or None) and a string "content" on an event whose source is tool_result, an
#      object or None as the "content" of an error or a refusal.
#   4. No source and no kind is new.

AGENT_SDK_MODES = ("default", "acceptEdits", "plan", "bypassPermissions", "dontAsk", "auto")
AGENT_SDK_TOOL_USES = ("tool_use", "server_tool_use", "mcp_tool_use")
AGENT_SDK_ASKING_HOOKS = ("PreToolUse", "PermissionRequest")
# What is kept of the options, and of each sub-agent's definition. The recorder writes no other field, and the
# converter reads no other field of a file that was written by hand.
AGENT_SDK_LISTS = ("allowed_tools", "disallowed_tools", "mcp_servers")
AGENT_SDK_DEFINITION_FIELDS = (
    "description",
    "prompt",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
)
ARRIVED = "stream"  # the sender of text that arrived in the stream and that the recorder did not see your code send
KINDS_OF_VALUE = {
    str: "text",
    list: "a list",
    dict: "an object",
    bool: "true or false",
    int: "a number",
}


def short_code(value, otherwise="other"):
    """A value from a log as a short code (letters, digits and _ . : -, 64 at most): itself if it is one, and
    otherwise the word given. Only such a code, or a fixed word, goes into an event that speaks for the platform."""
    return value if isinstance(value, str) and value and SAFE_CODE.fullmatch(value) else otherwise


def kind_of_value(value):
    """What a value from a log is, in a reader's words: text, a number, a list, an object, true or false, or null."""
    if value is None:
        return "null"
    if isinstance(value, float):
        return "a number"
    return KINDS_OF_VALUE.get(type(value), "a value of type " + type(value).__name__)


def agent_sdk_options(options, where, need):
    """The fixed list of what a log may say that your code set, each held to its shape: the system prompt, the
    tools, the two lists of permission rules, the permission mode, the model, the limit on turns, the names of the
    MCP servers, and of each sub-agent its description, prompt, tools, disallowed tools, model and permission
    mode. Anything else in the file's options is left out, so that a file written by hand can't put a server's
    settings or a token into the transcript."""
    where("options")
    prompt = options.get("system_prompt")
    if isinstance(prompt, dict):  # a preset, whose own text your code does not hold
        prompt = {
            "preset": short_code(prompt.get("preset")),
            "append": need(prompt.get("append") or "", str, "system_prompt.append"),
        }
    elif prompt is not None:
        need(prompt, str, "system_prompt")
    tools = options.get("tools")
    if isinstance(tools, dict):
        tools = {"preset": short_code(tools.get("preset"))}
    elif tools is not None:
        tools = [t for t in need(tools, list, "tools") if isinstance(t, str)]
    mode = options.get("permission_mode")
    kept = {
        "system_prompt": prompt,
        "tools": tools,
        "permission_mode": mode if isinstance(mode, str) and mode in AGENT_SDK_MODES else None,
        "model": options.get("model") if isinstance(options.get("model"), str) else None,
        "max_turns": options.get("max_turns") if type(options.get("max_turns")) is int else None,
        "agents": {},
    }
    for name in AGENT_SDK_LISTS:
        kept[name] = [v for v in need(options.get(name) or [], list, name) if isinstance(v, str)]
    for name, definition in need(options.get("agents") or {}, dict, "agents").items():
        where(f"options, the sub-agent {short_code(name)}")
        need(definition, dict, "its definition")
        keep = {}
        for key in AGENT_SDK_DEFINITION_FIELDS:
            value = definition.get(key)
            if key in ("tools", "disallowedTools") and value is not None:
                keep[key] = [t for t in need(value, list, key) if isinstance(t, str)]
            elif key == "permissionMode" and value is not None:
                keep[key] = value if isinstance(value, str) and value in AGENT_SDK_MODES else None
            elif value is not None:
                keep[key] = need(value, str, key)
        kept["agents"][name] = keep
    return kept


def normalize_agent_sdk(log, deployment, first_message_is_task):
    """One Agent SDK log (see LoggedAgentSession) -> session record.

    A prompt is the task or a user's message only if the recorder saw your code send it. Text that arrived in the
    stream as a user message and is not a tool result (an injected turn, a task notification, a peer's message, a
    replayed prompt) is kept as content the agent received: source tool_result, kind thread_message, sender
    "stream". It is never dropped by comparing it with a prompt, since that would let the log decide what the
    reviewer is not shown.

    A denied call gets a permission event with decision "deny", after its call, however the log reports it (the
    result message's permission_denials, a permission_denied message, or both). An approval that the recorder
    logged gets a permission event with decision "ask" and a confirmation with its answer. A deny stands whichever
    way it was reported: a call that was answered "allow" and that the log also lists as denied gets its deny too.
    Notes at the end of the record say where denials may be missing: the log ends without a result message, a
    permission callback was set and its answers were not logged, a hook that can deny was set, or an approval
    names no call.

    A session that your code took up again (a resumed session) is one record: where the second run begins, the
    record says so, and gives the options of that run if they differ.

    A missing field, or a field of the wrong kind, raises a ValueError that says where in the log it was."""
    ctx = {"where": "the log header"}
    try:
        return _normalize_agent_sdk(log, deployment, first_message_is_task, ctx)
    except (KeyError, TypeError, AttributeError) as exc:
        raise shape_error(ctx["where"], exc) from exc


def _normalize_agent_sdk(log, deployment, first_message_is_task, ctx):
    def where(place):
        ctx["where"] = place

    def need(value, kinds, what):
        wanted = kinds if isinstance(kinds, tuple) else (kinds,)
        if not isinstance(value, wanted) or isinstance(value, bool):
            expected = " or ".join("null" if k is type(None) else KINDS_OF_VALUE[k] for k in wanted)
            raise ValueError(
                f"{ctx['where']}: {what} should be {expected}, and is {kind_of_value(value)}"
            )
        return value

    def plain(call_id):
        return call_id if isinstance(call_id, str) and SAFE_ID.fullmatch(call_id) else None

    where("the log header")
    entries = need(log["entries"], list, "entries")
    rb = RecordBuilder(
        {
            "id": log["session_id"],
            "log_source": "agent_sdk",
            "agent": need(log["agent"], str, "agent"),
            "agent_version": "" if log.get("agent_version") is None else str(log["agent_version"]),
            "deployment": deployment,
            "started_at": log["started_at"],
            "ended_at": log["ended_at"],
        }
    )

    # First, what an event may depend on that comes later in the log: which calls were denied or answered, what
    # each run of your code set, and what the runtime reported at the start of each.
    where("options")
    runs = [
        {
            "options": agent_sdk_options(
                need(log.get("options") or {}, dict, "options"), where, need
            ),
            "recorder": need(log.get("recorder") or {}, dict, "recorder"),
            "init": None,
            "spoke": False,
            "said": "recorder" in log,
        }
    ]
    calls, denied, answers, nameless, left_out = {}, {}, {}, [], Counter()
    open_turn = False  # whether the agent has acted since the last result message
    for n, entry in enumerate(entries):
        where(f"entry {n}")
        need(entry, dict, "the entry")
        if "resumed" in entry:
            again = need(entry["resumed"], dict, "resumed")
            runs.append(
                {
                    "options": agent_sdk_options(
                        need(again.get("options") or {}, dict, "options"), where, need
                    ),
                    "recorder": need(again.get("recorder") or {}, dict, "recorder"),
                    "init": None,
                    "spoke": False,
                    "said": "recorder" in again,
                    "at": n,
                }
            )
            continue
        if "approval" in entry:
            approval = need(entry["approval"], dict, "approval")
            allowed = approval.get("decision") == "allow"  # an answer that is not "allow" is a deny
            call_id = approval.get("tool_use_id")
            if not isinstance(call_id, str):
                nameless.append((n, allowed))
            else:  # a deny is never undone by an allow for the same call
                answers[call_id] = "allow" if allowed and answers.get(call_id) != "deny" else "deny"
            continue
        if "sent" in entry:
            open_turn = True  # a prompt that no result message answers is an open turn too
            continue
        message = entry.get("message")
        kind = message.get("type") if isinstance(message, dict) else None
        subtype = message.get("subtype") if isinstance(message, dict) else None
        if kind == "assistant":
            runs[-1]["spoke"], open_turn = True, True
            content = need(message["message"], dict, "message")["content"]
            for block in need(content, list, "content"):
                if isinstance(block, dict) and block.get("type") in AGENT_SDK_TOOL_USES:
                    if isinstance(block.get("id"), str):
                        calls.setdefault(block["id"], (block, message.get("parent_tool_use_id")))
        elif kind == "user":
            open_turn = True
        elif kind == "system" and subtype == "init":
            if runs[-1]["init"] is None and not runs[-1]["spoke"]:
                runs[-1]["init"] = message
        elif kind == "system" and subtype == "permission_denied":
            if isinstance(message.get("tool_use_id"), str):
                reason = short_code(message.get("decision_reason_type"), None)
                denied[message["tool_use_id"]] = denied.get(message["tool_use_id"]) or reason
        elif kind == "system" and subtype == "compact_boundary":
            pass
        elif kind == "result":
            open_turn = False
            for denial in need(message.get("permission_denials") or [], list, "permission_denials"):
                if isinstance(denial, dict) and isinstance(denial.get("tool_use_id"), str):
                    denied.setdefault(denial["tool_use_id"], None)
        else:  # a kind of message, or of entry, that the converter does not read
            named = "no-type" if kind is None else short_code(kind)
            left_out[f"{named}/{'-' if subtype is None else short_code(subtype)}"] += 1

    def environment(run):
        """What one run of your code set, as the two environment events, with what the runtime reported kept apart."""
        options, init = run["options"], run["init"] or {}
        where("the first init message")
        prompt = options["system_prompt"]
        rb.add(
            source="environment",
            kind="system_prompt",
            thread="main",
            content=prompt["append"] if isinstance(prompt, dict) else prompt or "",
        )
        if isinstance(prompt, dict):
            rb.add(
                source="note",
                kind="unshown_block",
                thread="main",
                content="The log holds what you appended to the system prompt and not the preset's own text.",
            )

        def codes(value):
            return (
                [short_code(v) for v in value if isinstance(v, str)]
                if isinstance(value, list)
                else []
            )

        servers = init.get("mcp_servers")
        named = (
            [s.get("name") if isinstance(s, dict) else s for s in servers]
            if isinstance(servers, list)
            else []
        )
        reported = init.get("permissionMode")
        rb.add(
            source="environment",
            kind="tool_definitions",
            thread="main",
            content={
                "tools": options["tools"],
                "max_turns": options["max_turns"],
                "allowed_tools": options["allowed_tools"],
                "disallowed_tools": options["disallowed_tools"],
                "permission_mode": options["permission_mode"],
                "mcp_servers": options["mcp_servers"],
                "agents": options["agents"],
                "reported_by_the_runtime": {
                    "tools": codes(init.get("tools")),
                    "permission_mode": reported
                    if isinstance(reported, str) and reported in AGENT_SDK_MODES
                    else None,
                    "agents": codes(init.get("agents")),
                    "mcp_servers": codes(named),
                },
            },
        )

    environment(runs[0])
    run, resumed = runs[0], {r["at"]: r for r in runs[1:]}
    threads, judged, said = {}, set(), set()
    texts = set()

    def thread_of(message):
        parent = message.get("parent_tool_use_id")
        if parent is None:
            return "main", None
        need(parent, str, "parent_tool_use_id")
        if parent not in threads:
            label = f"sub-agent {len(threads) + 1}"
            given = calls.get(parent, ({}, None))[0].get("input")
            name = given.get("subagent_type") if isinstance(given, dict) else None
            # Only a name that your own code declared, and that is a short code, may name a thread.
            if (
                isinstance(name, str)
                and name in run["options"]["agents"]
                and short_code(name, None)
            ):
                label += f" ({name})"
            threads[parent] = label
        return threads[parent], parent

    def thread_of_call(call_id):
        """The thread of a call that the log holds, for a permission event that comes before or after it."""
        parent = calls.get(call_id, (None, None))[1]
        return threads.get(parent, "main") if isinstance(parent, str) else "main"

    def arrived(thread, text, origin):
        """Text that arrived in the stream and that the recorder did not see your code send. Cut like a tool result."""
        kind = origin.get("kind") if isinstance(origin, dict) else None
        ev = rb.add(
            source="tool_result",
            kind="thread_message",
            thread=thread,
            sender=f"{ARRIVED}:{short_code(kind)}" if kind is not None else ARRIVED,
            call_id=None,
            is_error=False,
            content=text,
            elided_chars=0,
        )
        if len(text) > MAX_RESULT_CHARS:
            cut, half = len(text) - MAX_RESULT_CHARS, MAX_RESULT_CHARS // 2
            ev["content"], ev["elided_chars"] = text[:half] + "\n[…]\n" + text[-half:], cut
            rb.uncut[str(ev["i"])] = text
            rb.notes.append(
                f"Text at event {ev['i']} cut: {cut:,} of {len(text):,} characters removed between head and tail."
            )

    def permission(thread, call_id, decision, reason=None):
        rb.add(
            source="platform",
            kind="permission",
            thread=thread,
            call_id=plain(call_id),
            decision=decision,
            reason=reason,
            policy=run["options"]["permission_mode"],
        )

    def confirmation(thread, call_id, decision):
        rb.add(
            source="platform",
            kind="confirmation",
            thread=thread,
            call_id=plain(call_id),
            decision=decision,
            content=None,
        )

    def judge(thread, call_id):
        """The permission events of a call, once. A logged answer is an ask and a confirmation. A denial is a deny,
        also after an answer of "allow": a deny stands whichever way it was reported."""
        if call_id in judged or (call_id not in answers and call_id not in denied):
            return
        judged.add(call_id)
        if call_id in answers:
            permission(thread, call_id, "ask")
            confirmation(thread, call_id, answers[call_id])
        if call_id in denied and answers.get(call_id) != "deny":
            permission(thread, call_id, "deny", denied[call_id])

    sent = 0
    for n, entry in enumerate(entries):
        where(f"entry {n}")
        if n in resumed:
            before, run = run, resumed[n]
            rb.notes.append(
                f"At event {len(rb.events)} the session was taken up again by a new run of your code."
            )
            if run["options"] != before["options"] or run["init"] is not None:
                environment(run)
            continue
        if "sent" in entry:
            is_task = sent == 0 and first_message_is_task
            rb.add(
                source="environment" if is_task else "user",
                kind="task" if is_task else "message",
                thread="main",
                content=need(entry["sent"], str, "sent"),
            )
            sent += 1
            continue
        if "approval" in entry:
            if (n, False) in nameless:  # a refused approval that names no call is kept, with no id
                confirmation("main", None, "deny")
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        kind = message.get("type")
        where(f"entry {n} ({short_code(kind, 'a message of no known type')})")
        if kind == "assistant":
            thread, _ = thread_of(message)
            inner = message["message"]
            for k, block in enumerate(inner["content"]):
                where(f"entry {n} (assistant), block {k}")
                what = need(block, dict, "the block")["type"]
                if what == "text":
                    rb.add(
                        source="agent",
                        kind="text",
                        thread=thread,
                        content=need(block["text"], str, "text"),
                    )
                    texts.add(thread)
                elif what == "thinking":
                    thinking = block.get("thinking")
                    rb.add(
                        source="agent",
                        kind="reasoning",
                        thread=thread,
                        content=thinking if isinstance(thinking, str) and thinking else None,
                    )
                elif what == "redacted_thinking":
                    rb.add(source="agent", kind="reasoning", thread=thread, content=None)
                elif what in AGENT_SDK_TOOL_USES:
                    rb.add(
                        source="agent",
                        kind="tool_call",
                        thread=thread,
                        tool=need(block["name"], str, "name"),
                        call_id=need(block["id"], str, "id"),
                        input=need(block.get("input") or {}, dict, "input"),
                    )
                    judge(thread, block["id"])
                elif isinstance(what, str) and what.endswith("tool_result"):
                    call_id = need(block.get("tool_use_id"), (str, type(None)), "tool_use_id")
                    rb.result(thread, call_id, block.get("content"), block.get("is_error"))
                else:
                    rb.add(
                        source="note",
                        kind="unshown_block",
                        thread=thread,
                        content=f"A block of type {short_code(what, 'unknown')} isn't shown.",
                    )
            where(f"entry {n} (assistant)")
            once = inner.get("id") if isinstance(inner.get("id"), str) else f"entry {n}"
            if message.get("error") is not None and ("error", once) not in said:
                said.add(("error", once))
                rb.add(
                    source="platform",
                    kind="error",
                    thread=thread,
                    content={"type": short_code(message["error"]), "message": ""},
                )
            if inner.get("stop_reason") == "refusal" and ("refusal", once) not in said:
                said |= {("refusal", once), "refused"}
                details = inner.get("stop_details")
                category = (
                    short_code(details.get("category"), None) if isinstance(details, dict) else None
                )
                rb.add(
                    source="platform",
                    kind="refusal",
                    thread=thread,
                    content={"category": category} if category else None,
                )
        elif kind == "user":
            thread, parent = thread_of(message)
            content = need(message["message"], dict, "message")["content"]
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            for k, block in enumerate(need(content, list, "content")):
                where(f"entry {n} (user), block {k}")
                what = need(block, dict, "the block")["type"]
                if what == "tool_result":
                    call_id = need(block["tool_use_id"], str, "tool_use_id")
                    # If the log lacks the call itself, its permission events go before its result.
                    judge(thread, call_id)
                    rb.result(thread, call_id, block.get("content"), block.get("is_error"))
                elif what == "text":
                    text = need(block["text"], str, "text")
                    given = calls.get(parent, ({}, None))[0].get("input") if parent else None
                    if isinstance(given, dict) and given.get("prompt") == text:
                        rb.add(source="agent", kind="brief", thread=thread, content=text)
                    else:
                        arrived(thread, text, message.get("origin"))
                else:
                    rb.add(
                        source="note",
                        kind="unshown_block",
                        thread=thread,
                        content=f"A block of type {short_code(what, 'unknown')} isn't shown.",
                    )
        elif kind == "system" and message.get("subtype") == "compact_boundary":
            rb.add(
                source="note",
                kind="context_compacted",
                thread="main",
                content="The agent's context was compacted here: it no longer had the earlier events in view.",
            )
        elif kind == "result":
            subtype, status = message.get("subtype"), message.get("api_error_status")
            code = None
            if isinstance(subtype, str) and subtype.startswith("error"):
                code = short_code(subtype)
            elif message.get("is_error"):
                code = (
                    short_code(f"api_error_{status}", "error") if type(status) is int else "error"
                )
            if code:
                rb.add(
                    source="platform",
                    kind="error",
                    thread="main",
                    content={"type": code, "message": ""},
                )
            errors = message.get("errors")
            count = (
                len(errors) if isinstance(errors, list) else errors if type(errors) is int else 0
            )
            if count > 0:
                rb.notes.append(
                    f"A result message held {count} error string{'' if count == 1 else 's'}, which "
                    f"{'is' if count == 1 else 'are'} not shown: this transcript gives an error from the SDK by its code "
                    f"alone, never its text. To read {'it' if count == 1 else 'them'}, print the result message in your own code."
                )
            if message.get("stop_reason") == "refusal" and "refused" not in said:
                rb.add(source="platform", kind="refusal", thread="main", content=None)
            said.discard("refused")

    where("the denied calls that no call in the log matches")
    for call_id in [c for c in (*answers, *denied) if c not in judged]:
        judge(thread_of_call(call_id), call_id)

    where("the notes")
    for thread in threads.values():
        if thread not in texts and not any(
            r["recorder"].get("forward_subagent_text") is True for r in runs
        ):
            rb.notes.append(
                f"The text of {thread} isn't in the log: the SDK leaves a sub-agent's text out of the stream "
                "unless forward_subagent_text is set."
            )
    if left_out:
        kinds = ", ".join(f"{kind} ({n})" for kind, n in sorted(left_out.items())[:12])
        rb.notes.append(
            f"{sum(left_out.values())} entries of kinds that the converter does not read were left out, "
            f"by type and subtype: {kinds}{' and more' if len(left_out) > 12 else ''}."
        )
    if open_turn:
        rb.notes.append(
            "The log ends without a result message, so calls that were denied may be missing from it."
        )
    if nameless:
        refused = sum(1 for _, allowed in nameless if not allowed)
        rb.notes.append(
            f"{len(nameless)} logged approval{'' if len(nameless) == 1 else 's'} named no call, {refused} of them "
            "refused, so the call that each was about is not marked."
        )
    if any(r["recorder"].get("beside") is True for r in runs):
        rb.notes.append(
            "When this log was begun, a file with this session's name was already in its folder. It was left as it "
            "is, and this log was written beside it."
        )
    if any(r["recorder"].get("moved_beside") is True for r in runs):
        rb.notes.append(
            "While this session was being recorded, another writer wrote to the file of this log's name. That file "
            "was left as it is, and this log was written beside it, so the folder may hold two logs of this session."
        )
    if not all(r["said"] for r in runs):
        rb.notes.append(
            "The log has no recorder block, so it doesn't say whether a permission callback or hook was set. A call "
            "that one of them denied may show only as an error in a tool result."
        )
    for r in runs:
        named = r["recorder"].get("hooks")
        hooks = [h for h in named if h in AGENT_SDK_ASKING_HOOKS] if isinstance(named, list) else []
        unlogged = r["recorder"].get("permission_callback") and not r["recorder"].get(
            "approvals_recorded"
        )
        if hooks or unlogged:
            if hooks and unlogged:
                start = (
                    "A hook that can deny a call and a permission callback were set, and their answers were not "
                    "logged, so a call that one of them denied"
                )
            elif hooks:
                start = "A hook that can deny a call was set, and its answers are not logged, so a call that it denied"
            else:
                start = "A permission callback was set and its answers were not logged, so a call that it denied"
            rb.notes.append(start + " may show only as an error in a tool result.")
            break
    return rb.record()


# --- Getting logs: export, collect, load ------------------------------------------------

REVIEW_AGENT_NAME = (
    "agent-log-reviewer"  # the review agent's name: collection skips its own sessions
)
NORMALIZERS = {
    "managed_agents": normalize_managed_agents,
    "messages_api": normalize_messages_api,
    "agent_sdk": normalize_agent_sdk,
}


def parse_time(text):
    """An ISO 8601 timestamp as an aware datetime. A timestamp or date with no offset is read as UTC."""
    try:
        when = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{text!r} is not a timestamp: use UTC, such as 2026-10-01T00:00:00Z"
        ) from exc
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def thread_agent_name(agent):
    """A thread's agent name. An advisor thread's agent has a model and no name."""
    name = getattr(agent, "name", None)
    if name:
        return name
    model = getattr(agent, "model", None)
    return f"{getattr(agent, 'type', None) or 'agent'} ({getattr(model, 'id', model)})"


def private_dir(path):
    """Create a folder (and any parents that don't exist yet) readable only by you, mode 0o700. Folders that already
    exist are left as they are."""
    path = Path(path)
    for folder in reversed([p for p in (path, *path.parents) if not p.exists()]):
        folder.mkdir(mode=0o700, exist_ok=True)
        os.chmod(folder, 0o700)  # mkdir's mode is filtered by the umask


def logs_dir(path):
    """Make ready the folder that whole transcripts are about to be written into, on a machine that others may
    use too, and return it.

    The helper's own folder, which is my_logs_dir's, is made strictly: every folder from your home directory down
    to it is made with mode 0o700 if it is not there, and must then be a real folder that is yours and that
    nobody else can write. Your home directory may itself be a link; below it a link is refused. Otherwise a
    ValueError names the folder that stands in the way. A folder that the system does not let you make raises
    the system's own error, a PermissionError.

    A folder that you name yourself is made if it is not there, and is otherwise left as it is: its mode is
    not changed, and a link is followed. If the folder is not yours, or others can read, write or enter it, one
    printed line says so. Each transcript is written as a file that only you can read (see private_write).

    Where the system has no owners and modes, as on Windows, nothing is checked."""
    path = Path(path)
    if not hasattr(os, "getuid"):
        private_dir(path)
        return path
    me = os.getuid()
    try:
        home = Path(os.path.realpath(Path.home()))
        # Any name will do for the question: the folder asked for is the one that holds every agent's logs.
        own = path.relative_to(my_logs_dir("x").parent).parts
    except (RuntimeError, ValueError):
        own = None  # no home directory, or a folder of your own naming
    if own is None:
        private_dir(path)
        found = path.stat()
        if found.st_uid != me:
            print(
                f"{path} belongs to another user, who can see the names of your logs, remove them and put "
                "others in their place. Use a folder of your own."
            )
        elif found.st_mode & 0o077:
            reads, writes = found.st_mode & 0o044, found.st_mode & 0o022
            what = (
                "read and written"
                if reads and writes
                else "written"
                if writes
                else "read"
                if reads
                else "entered"
            )
            print(
                f"{path} can be {what} by others (mode {found.st_mode & 0o777:o}). Each log is "
                "written so that only you can read it; to keep others out of the folder, run chmod 700 on it."
            )
        return path
    part = home
    for name in (None, ".cache", "agent_log_review", "logs", *own):
        part = part if name is None else part / name
        with contextlib.suppress(
            FileExistsError
        ):  # whatever is there, or appears meanwhile, is looked at next
            os.mkdir(part, 0o700)
        found = os.lstat(part)
        if not stat.S_ISDIR(found.st_mode) or found.st_uid != me or found.st_mode & 0o022:
            what = (
                "is a link, or not a folder"
                if not stat.S_ISDIR(found.st_mode)
                else "belongs to another user"
                if found.st_uid != me
                else "can be written by others"
            )
            raise ValueError(
                f"{part} {what}, so logs are not written under it. Give collect_managed_agents a folder of "
                "your own."
            )
    return part


def private_write(path, text):
    """Write a file readable only by you, mode 0o600, in a folder made private if it is new. Transcripts can hold any
    secret the agents saw, so the logs and the audit trail are written this way. In a folder that others can
    write, another user may have put a link or a file of their own under the file's name: a symbolic link is
    not followed, and a file that is not yours is not written into, whoever you are. A ValueError says so. A
    file that the system does not let you open raises the system's own error, a PermissionError."""
    path = Path(path)
    private_dir(path.parent)
    try:
        careful = getattr(os, "O_NOFOLLOW", 0) | getattr(
            os, "O_NONBLOCK", 0
        )  # no link followed, no pipe waited for
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | careful, 0o600)
    except OSError as why:
        if os.path.islink(path):
            raise ValueError(
                f"{path} is a link, so nothing is written through it. Remove it, or use another folder."
            ) from why
        if os.path.lexists(path) and not stat.S_ISREG(os.lstat(path).st_mode):
            raise ValueError(
                f"{path} is not a file of yours, so nothing is written into it. Remove it, or use another folder."
            ) from why
        raise
    found = os.fstat(fd)
    if not stat.S_ISREG(found.st_mode) or (hasattr(os, "getuid") and os.getuid() != found.st_uid):
        # Root is refused like anyone else: the owner of a file that is not root's could read what is written.
        os.close(fd)
        raise ValueError(
            f"{path} is not a file of yours, so nothing is written into it. Remove it, or use another folder."
        )
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)  # a file that already existed keeps its old mode through O_CREAT
    os.ftruncate(fd, 0)  # only now, so that a file that is not yours is left as it was
    # A lone surrogate, which valid JSON can hold, can't be encoded as UTF-8: it is written as its escape.
    with os.fdopen(fd, "w", encoding="utf-8", errors="backslashreplace") as handle:
        handle.write(text)


def unique_threads(threads):
    """The threads of a listing, each once, in the order listed (the first listing of an id wins)."""
    seen = {}
    for thread in threads:
        seen.setdefault(thread.id, thread)
    return list(seen.values())


def thread_record(thread, events, agent_name=None):
    """One thread for an export: its id, its parent, its agent's name and its events as plain JSON. With no thread,
    the record stands for the primary thread."""
    return {
        "id": thread.id if thread else "primary",
        "parent_thread_id": thread.parent_thread_id if thread else None,
        "agent_name": thread_agent_name(thread.agent) if thread else agent_name,
        "events": [e.model_dump(mode="json") for e in events],
    }


def threads_not_held(exported, also=()):
    """The ids of the threads that an export's records should hold and don't, in the order they were created:
    every thread that a session.thread_created event of the primary thread names, and every id in also. A record
    with no events does not count as held. The thread list may leave out threads that have ended, so an export
    reads these by id, and the review session is deleted only when none is left (see review_session)."""
    held = {t.get("id") for t in exported if t.get("events")}
    named = [
        e.get("session_thread_id")
        for t in exported
        if t.get("parent_thread_id") is None
        for e in t.get("events") or []
        if e.get("type") == "session.thread_created"
    ]
    return [t for t in dict.fromkeys([*named, *also]) if isinstance(t, str) and t not in held]


def export_session(client, betas, session_id):
    """Everything the review needs from one Managed Agents session, as plain JSON. The agent is the snapshot the
    session ran (session.agent), not the agent's current version. If the thread list has no primary thread, the
    session's own event list stands in for it. A thread that the primary thread's events name and the list
    leaves out is read by its id."""
    sessions = client.beta.sessions
    session = sessions.retrieve(session_id, betas=betas)
    threads = unique_threads(sessions.threads.list(session_id, betas=betas))
    exported = [
        thread_record(t, sessions.threads.events.list(t.id, session_id=session_id, betas=betas))
        for t in threads
    ]
    if not any(t["parent_thread_id"] is None for t in exported):
        events = sessions.events.list(session_id, betas=betas, order="asc")
        exported.insert(0, thread_record(None, events, agent_name=session.agent.name))
    # The list can leave out the threads that have ended: those are read by id.
    for thread_id in threads_not_held(exported):
        with contextlib.suppress(anthropic.NotFoundError):
            t = sessions.threads.retrieve(thread_id, session_id=session_id, betas=betas)
            events = sessions.threads.events.list(t.id, session_id=session_id, betas=betas)
            exported.append(thread_record(t, events))
    return {
        "log_format": "managed_agents_export",
        "session": session.model_dump(mode="json"),
        "agent": session.agent.model_dump(mode="json"),
        "threads": exported,
    }


class Collected(list):
    """The ids of sessions that were still running (collect them next time). .failed lists {"session", "why"} for each
    export that failed."""

    def __init__(self):
        super().__init__()
        self.failed = []


def collect_managed_agents(
    client,
    betas,
    window_start_iso,
    out_dir,
    agent_id=None,
    lookback_iso=None,
    session_ids=(),
    export_one=None,
):
    """Export every finished session that changed since window_start_iso into out_dir, one JSON file each.

    A timestamp with no offset is read as UTC. Sessions are listed by creation time, so the listing starts a day
    before the window (or at lookback_iso) to catch long sessions created earlier. Archived sessions are included.
    With no agent_id, this cookbook's own review sessions are skipped. Only idle and terminated sessions are
    exported; running and rescheduling ones are returned, to collect next time: pass them back as session_ids,
    and they are exported first, or returned again if still unfinished. An export that fails is listed in the
    result's .failed and printed; it doesn't stop the others. export_one(client, betas, session_id) exports one
    session; it is export_session unless you pass your own."""
    export_one = export_one or export_session
    window_start = parse_time(window_start_iso)
    lookback = parse_time(lookback_iso) if lookback_iso else window_start - timedelta(days=1)
    out_dir = logs_dir(out_dir)
    finished, collected, seen = ("idle", "terminated"), Collected(), set(session_ids)

    def export(session_id):
        try:
            private_write(
                out_dir / f"{session_id}.json",
                json.dumps(export_one(client, betas, session_id)),
            )
        except Exception as exc:  # one session's export failing shouldn't lose the rest
            collected.failed.append({"session": session_id, "why": f"{type(exc).__name__}: {exc}"})

    for session_id in session_ids:
        if client.beta.sessions.retrieve(session_id, betas=betas).status in finished:
            export(session_id)
        else:
            collected.append(session_id)
    query = {"created_at_gte": lookback, "include_archived": True, "betas": betas}
    if agent_id:
        query["agent_id"] = agent_id
    for session in client.beta.sessions.list(**query):
        updated = (
            session.updated_at
            if isinstance(session.updated_at, datetime)
            else parse_time(session.updated_at)
        )
        if session.id in seen or updated < window_start:
            continue
        if not agent_id and getattr(session.agent, "name", None) == REVIEW_AGENT_NAME:
            continue
        if session.status in finished:
            export(session.id)
        else:
            collected.append(session.id)
    if collected.failed:
        print(f"Couldn't export {len(collected.failed)} sessions:")
        for f in collected.failed:
            print(f"  {f['session']}: {f['why']}")
    return collected


class Loaded(NamedTuple):
    records: dict  # session id -> record
    skipped: list  # [{"file", "why"}] for each log that couldn't be read or converted
    files: dict  # session id -> file name


# A session id and a platform's reason code go into the task a review step is given, so they may hold only these:
# nothing that could make them read as words to the reviewer.
SAFE_ID = re.compile(r"[A-Za-z0-9._:/@+=-]{1,128}")
SAFE_CODE = re.compile(r"[A-Za-z0-9_.:-]{0,64}")


def id_problem(session_id):
    """Why a session id can't be used, or None. The id is put into the task of the step that reviews the session,
    so it may hold no space, line break, quote or other character that could make it read as words: only letters,
    digits and . _ : / @ + = - are allowed, 128 at most."""
    if not isinstance(session_id, str) or not SAFE_ID.fullmatch(session_id):
        return (
            "the session id may hold only letters, digits and . _ : / @ + = - (128 at most), because it goes "
            f"into the reviewer's task; this one is {str(session_id)[:40]!r}"
        )
    return None


def log_problem(log, source):
    """Why a log can't be converted for this log_source, or None."""
    if not isinstance(log, dict):
        return "the file is not a JSON object"
    if source == "agent_sdk":
        if log.get("log_format") == "managed_agents_export" or "threads" in log:
            return 'this is a Managed Agents export, but its agent\'s log_source in AGENTS is "agent_sdk"'
        if log.get("log_format") == "messages_api_exchanges" or "exchanges" in log:
            return (
                'this is a Messages API log, but its agent\'s log_source in AGENTS is "agent_sdk"'
            )
        required = ("session_id", "agent", "started_at", "ended_at", "entries")
        missing = [k for k in required if k not in log]
        if missing:
            return (
                f"missing {', '.join(repr(k) for k in missing)} (required: {', '.join(required)})"
            )
        if not isinstance(log["entries"], list) or not log["entries"]:
            return (
                "'entries' is empty or not a list, so the log holds no session (was the recorder given any "
                "message?)"
            )
        for name in ("started_at", "ended_at"):
            try:
                if not isinstance(log[name], str):
                    raise ValueError
                parse_time(log[name])
            except ValueError:
                return (
                    f"'{name}' should be a time as text, such as 2026-10-01T00:00:00Z, and is "
                    f"{kind_of_value(log[name]) if not isinstance(log[name], str) else repr(log[name][:40])}"
                )
        return id_problem(log["session_id"])
    if log.get("log_format") == "agent_sdk_messages" or ("entries" in log and "recorder" in log):
        return f'this is an Agent SDK log, but its agent\'s log_source in AGENTS is "{source}"'
    if source == "messages_api":
        if log.get("log_format") == "managed_agents_export" or "threads" in log:
            return 'this is a Managed Agents export but log_source is "messages_api"'
        required = ("session_id", "agent", "started_at", "ended_at", "exchanges")
        missing = [k for k in required if k not in log]
        if missing:
            return (
                f"missing {', '.join(repr(k) for k in missing)} (required: {', '.join(required)})"
            )
        if not log["exchanges"]:
            return "'exchanges' is empty"
        last = log["exchanges"][-1]
        if (
            not isinstance(last, dict)
            or "request" not in last
            or not isinstance(last.get("response"), dict)
        ):
            return "the last exchange has no 'response' (did the last call fail?)"
        if "content" not in last["response"]:
            return "the last response has no 'content' (an error body?)"
        return id_problem(log["session_id"])
    else:
        if "exchanges" in log and "threads" not in log:
            return 'this is a Messages API log but log_source is "managed_agents"'
        missing = [k for k in ("session", "agent", "threads") if k not in log]
        if missing:
            return f"missing {', '.join(repr(k) for k in missing)} (an export_session file has session, agent and threads)"
        if isinstance(log["session"], dict) and "id" in log["session"]:
            return id_problem(log["session"]["id"])
    return None


def load_records(folder, deployment, grant):
    """Convert every *.json log in folder with the converter for the deployment's log_source.

    A log that is unreadable or missing what the converter needs is skipped and listed in .skipped with the file name
    and the reason (for a missing field, where in the log it was), so one bad file never stops the batch. A session
    id that an earlier file already had skips the later file, and says so. A "first_message_is_task" key in a log
    overrides the grant's setting for that log."""
    folder, source = Path(folder), grant.get("log_source")
    if source not in NORMALIZERS:
        raise ValueError(
            f"{deployment}: log_source must be one of {', '.join(NORMALIZERS)} (got {source!r})"
        )
    paths = sorted(folder.glob("*.json"))
    loaded = Loaded({}, [], {})
    if not paths:
        print(f"{deployment}: no *.json logs in {folder}, so nothing to review from this agent.")
        return loaded
    for path in paths:
        record, name = None, f"{folder.name}/{path.name}"
        try:
            text = path.read_text()
            if not text.strip():
                problem = "the file is empty"
            else:
                log = json.loads(text)
                problem = log_problem(log, source)
                if problem is None:
                    record = NORMALIZERS[source](
                        log,
                        deployment,
                        log.get("first_message_is_task", grant.get("first_message_is_task", False)),
                    )
                    # An id that is not text would stop the rules later, so such a log is skipped here.
                    if any(
                        not isinstance(ev.get("call_id"), (str, type(None)))
                        for ev in record["events"]
                    ):
                        raise ValueError(
                            "a tool call's id in the log is not text, so this session will not be "
                            "reviewed. The platform writes ids as text: read this file yourself"
                        )
                    # Whatever is nested MAX_DEPTH levels deep is replaced by a list of its values (see
                    # not_too_deep), so that the rules' walks of the record do not fail on depth. The rules give
                    # each such event a hit, or the first event where only another part of the file is that deep.
                    flat = [not_too_deep(ev) for ev in record["events"]]
                    record["events"] = [ev for ev, _ in flat]
                    deep = [ev["i"] for ev, was in flat if was]
                    elsewhere = deeper_than(log, MAX_DEPTH)
                    for part in [key for key in record if key != "events"]:
                        record[part], was = not_too_deep(record[part])
                        elsewhere = elsewhere or was
                    if deep:
                        record["too_deep"] = deep
                    if elsewhere and not deep and record["events"]:
                        record["too_deep_elsewhere"] = record["events"][0]["i"]
        except json.JSONDecodeError as exc:
            problem = f"the file isn't valid JSON (probably cut off or edited): line {exc.lineno}, column {exc.colno}"
        except RecursionError:
            problem = (
                "the file's JSON is nested too deep to be read (objects or lists inside one another, thousands "
                "deep), so this session will not be reviewed. No honest log is nested so deep, and the agent "
                "under review may have made it so: read this session yourself"
            )
        except Exception as exc:  # any other unreadable or malformed file: skip it, say why
            problem = str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: {exc}"
        if problem is None and record["session"]["id"] in loaded.files:
            problem = f"session id {record['session']['id']} was already loaded from {loaded.files[record['session']['id']]}"
        if problem:
            loaded.skipped.append({"file": name, "why": problem})
            continue
        sid = record["session"]["id"]
        loaded.records[sid], loaded.files[sid] = record, name
        status = log["session"].get("status") if source == "managed_agents" else None
        if status in (
            "running",
            "rescheduling",
        ):  # collect_managed_agents never exports these; a hand-placed file might be
            print(
                f"Warning: {name}: the session's status is {status}, so its log may still be growing. "
                "Export it again once it has finished."
            )
    if loaded.skipped:
        print(f"{deployment}: skipped {len(loaded.skipped)} of {len(paths)} logs:")
        for s in loaded.skipped:
            print(f"  {s['file']}: {s['why']}")
    return loaded


def combine(loads):
    """Merge the Loaded results of several deployments into (records, skipped). A session id that an earlier
    deployment already had skips the later one, and says so."""
    records, files, skipped = {}, {}, []
    for loaded in loads:
        skipped += loaded.skipped
        for sid, record in loaded.records.items():
            if sid in records:
                skipped.append(
                    {
                        "file": loaded.files[sid],
                        "why": f"session id {sid} was already loaded from {files[sid]}",
                    }
                )
                print(
                    f"Skipped {loaded.files[sid]}: session id {sid} was already loaded from {files[sid]}."
                )
                continue
            records[sid], files[sid] = record, loaded.files[sid]
    if skipped and not records:
        raise ValueError(
            f"0 sessions loaded: all {len(skipped)} logs were skipped. The first reason: "
            f"{skipped[0]['file']}: {skipped[0]['why']} (the full list is printed above)"
        )
    if not records:
        print("No sessions were loaded, so there is nothing to review.")
    return records, skipped


def skipped_line(skipped):
    """One sentence for the end of Part 2: how many logs were skipped, and that those sessions go unreviewed."""
    if not skipped:
        return ""
    return f"{len(skipped)} logs were skipped (listed above), so their sessions are not reviewed."


def bare_host(value):
    """A hostname as the rules compare it: lower case, no scheme, port, path or wildcard; None if it isn't one."""
    host = str(value).strip().lower().rstrip(".")
    return host if host and not any(c in host for c in "*/:") else None


RECIPIENT_ENTRY = re.compile(
    r"[^@\s<>*,;\"']*@[a-z0-9-]+(?:\.[a-z0-9-]+)+"
)  # addr@domain or @domain
PLACEHOLDER = re.compile(r"<[^<>\n@]*[A-Za-z][^<>\n@]*>")  # the template's <fill this in> text
DESCRIPTION_HOST = re.compile(
    r"(?<![@\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)+\b"
)  # not the domain of an email address
# A line starting with one of these labels names things that are NOT allowed or not locked down: its hosts don't count.
UNALLOWED_LABELS = ("known gaps:", "explicitly off limits:")


def description_hosts(text):
    """Host names a sandbox description mentions, leaving out lines that describe what is off limits or not locked
    down, and words that look like file names."""
    hosts = set()
    for line in text.lower().splitlines():
        if line.strip().startswith(UNALLOWED_LABELS):
            continue
        for word in DESCRIPTION_HOST.findall(line):
            ext = word.rsplit(".", 1)[1]
            if ext.isalpha() and len(ext) > 1 and ext not in FILE_EXTENSIONS:
                hosts.add(word)
    return hosts


def check_deployments(grants, deployments):
    """Raise if a deployment you are loading logs for has no entry in AGENTS."""
    missing = [name for name in deployments if name not in grants]
    if missing:
        raise ValueError(
            f"no entry in AGENTS for: {', '.join(missing)}. Add one to AGENTS in Part 1 (copy an entry; "
            "it needs description, log_source and allowed_hosts), then re-run that cell."
        )


def validate_agents(agents, deployments=()):
    """Check the AGENTS entries against the logs you are loading, and tidy them in place. Each entry holds the
    agent's description (the prose the reviewer reads) and its grant (the fields the rules read).

    Raises one error listing every problem: a deployment with logs and no entry, a description that is missing
    or still has the template's <placeholder> text, a log_source that isn't managed_agents, messages_api or agent_sdk, a
    host that isn't a bare hostname such as api.example.com (no scheme, wildcard, port or path; a string where a list
    belongs), or an unknown name in context_only_rules (STRUCTURAL_RULES lists them). Hosts are lower-cased, and
    missing optional keys (credentials, allowed_recipients, allowed_hosts) get their empty defaults; null is
    read as empty; ignore_hosts, if present, is checked like allowed_hosts. first_message_is_task defaults to false,
    which treats the first message as a user's.

    Warnings, printed and returned, don't stop anything: a host the description mentions but allowed_hosts doesn't
    list, the reverse, and a description with only a few lines."""
    problems, warnings = [], []
    problems += [
        f'"{name}" has logs but no entry in AGENTS' for name in deployments if name not in agents
    ]
    for name, grant in agents.items():
        where = f'AGENTS["{name}"]'
        if grant.get("log_source") not in NORMALIZERS:
            problems.append(
                f"{where}: log_source must be one of {', '.join(NORMALIZERS)} (got {grant.get('log_source')!r})"
            )
        grant.setdefault("first_message_is_task", False)
        for key in ("credentials", "allowed_recipients", "allowed_hosts"):
            if grant.get(key) is None:
                grant[key] = {} if key == "credentials" else []
        for key in ("allowed_hosts", "ignore_hosts", "allowed_recipients", "context_only_rules"):
            if isinstance(grant.get(key), str):
                problems.append(f"{where}: {key} must be a list, not the string {grant[key]!r}")
                grant[key] = []
        for key in ("allowed_hosts", "ignore_hosts"):
            given = grant.get(key) or []
            hosts = [bare_host(h) for h in given]
            for entry, tidy in zip(given, hosts, strict=True):
                if tidy is None:
                    problems.append(
                        f"{where}: {key} entry {entry!r} must be a bare hostname such as api.example.com"
                    )
            if key in grant:
                grant[key] = [h for h in hosts if h]
        for credential, host in list(grant["credentials"].items()):
            if bare_host(host) is None:
                problems.append(
                    f'{where}: credentials "{credential}" host {host!r} must be a bare hostname'
                )
            else:
                grant["credentials"][credential] = bare_host(host)
        grant["allowed_recipients"] = [str(a).strip().lower() for a in grant["allowed_recipients"]]
        for entry in grant["allowed_recipients"]:
            if not RECIPIENT_ENTRY.fullmatch(entry):
                problems.append(
                    f"{where}: allowed_recipients entry {entry!r} must be an address such as sam@customer.example or "
                    "a whole domain such as @customer.example (no display name, no *)"
                )
        for rule in grant.get("context_only_rules") or []:
            if rule not in STRUCTURAL_RULES:
                problems.append(
                    f"{where}: context_only_rules has {rule!r}, which isn't one of: {', '.join(STRUCTURAL_RULES)}"
                )
        text = grant.get("description")
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{where}: description is missing; write it from TEMPLATE.txt")
            continue
        left = PLACEHOLDER.findall(text)
        if left:
            problems.append(
                f"{where}: the description still has placeholder text such as {left[0][:60]!r}"
            )
        if len([line for line in text.splitlines() if line.strip()]) < 5:
            warnings.append(
                f"{where}: the description has only a few lines; the template has about fourteen."
            )
        allowed, ignored = grant["allowed_hosts"], grant.get("ignore_hosts", [])
        for host in sorted(description_hosts(text)):
            if not host_allowed(host, allowed + ignored):
                warnings.append(
                    f"{where}: the description mentions {host}, which allowed_hosts doesn't list "
                    "(ignore this if it's only an email domain)."
                )
        for host in allowed:
            if host not in text.lower():
                warnings.append(
                    f"{where}: allowed_hosts lists {host}, which the description doesn't mention."
                )
    if problems:
        raise ValueError("AGENTS needs changes:\n  " + "\n  ".join(problems))
    for warning in warnings:
        print("Warning: " + warning)
    return warnings


def _plain(obj):
    """JSON for the pydantic objects an SDK call returns, when they are passed back in a later request."""
    return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else str(obj)


class LoggedSession:
    """Log a Messages API agent's calls in the shape load_records reads: one JSON file per session.

        log = LoggedSession(client, session_id="abc", agent="support-agent", folder="logs/support-desk")
        response = log.create(model=..., system=..., tools=..., messages=..., max_tokens=...)

    create() makes the call and writes the file after every exchange, so a crash loses nothing. The file holds each
    exchange's full request, so it grows with the square of the conversation's length. The file is named after the
    session id with anything other than letters, digits, dots, dashes and underscores replaced by an underscore (the
    real id is kept inside it), so an id such as "org/123" can't make a folder or leave the logs folder.

    For a call you make some other way, such as streaming or the async client, make it yourself and then pass the
    request and the final message to record():

        with client.messages.stream(**request) as stream:
            final = stream.get_final_message()
        log.record(request, final)          # async: final = await ...; log.record(request, final)"""

    def __init__(self, client, session_id, agent, folder, agent_version=None):
        self.client = client
        self.path = Path(folder) / (re.sub(r"[^A-Za-z0-9._-]", "_", session_id) + ".json")
        self.log = {
            "log_format": "messages_api_exchanges",
            "session_id": session_id,
            "agent": agent,
            **({"agent_version": str(agent_version)} if agent_version is not None else {}),
            "started_at": None,
            "ended_at": None,
            "exchanges": [],
        }
        private_dir(self.path.parent)

    @staticmethod
    def _now():
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def create(self, **request):
        started = self._now()
        return self.record(request, self.client.messages.create(**request), started_at=started)

    def record(self, request, response, started_at=None):
        """Log one exchange. started_at is when the call began (create() passes it); without it the time now is used."""
        now = self._now()
        self.log["started_at"] = self.log["started_at"] or started_at or now
        self.log["ended_at"] = now
        self.log["exchanges"].append(
            {
                "request": json.loads(json.dumps(request, default=_plain)),
                "response": response.model_dump(mode="json"),
            }
        )
        private_write(self.path, json.dumps(self.log))
        return response


class LoggedAgentSession:
    """Log an Agent SDK session in the shape load_records reads (log_source "agent_sdk"): one JSON file per session.

        log = lr.LoggedAgentSession(agent="brief-writer", folder=lr.my_logs_dir("brief-writer"), options=options)
        log.sent(prompt)
        async for message in query(prompt=prompt, options=options):
            log.record(message)

    Call sent() with the text of each prompt your code sends, and record() with each message the SDK gives you, in
    order. Only what sent() was given is shown to the reviewer as your task or as a user's message; text that
    arrives in the stream is shown as content the agent received. If you send your prompts as a stream, which the
    SDK requires when you pass can_use_tool, call sent() with each one's text as you yield it:

        async def prompts():
            log.sent(prompt)
            yield {"type": "user", "message": {"role": "user", "content": prompt}}

        options.can_use_tool = log.approvals(my_callback)  # before you call query
        async for message in query(prompt=prompts(), options=options):
            log.record(message)

    approvals() logs each request that your callback was asked and its answer. A hook is not asked through the
    callback, so what a PreToolUse hook denies is not logged; the transcript says so.

    The file is named after the session id: the one you give, or the first one the SDK reports, which is in its
    first message. Until the id is known, what you log waits in memory, and a crash would lose it; from then on the
    file is written whole after every message, so the cost of a long session grows with the square of its length.
    In the name, anything other than letters, digits, dots, dashes and underscores is replaced by an underscore, so
    an id can't make a folder or leave the logs folder. Where a file of that name is there already, it is taken up
    only if your options say that this session continues another (resume or continue_conversation, without
    fork_session) and the file is this session's log: the new messages then go after the old ones. In every other case it is left as it is
    and the log goes beside it, with -2, -3 and so on before ".json", and the transcript says so. So give each
    session an id of its own, and run one recorder on a session at a time: a recorder that finds its file changed
    by another writer leaves that file as it is and goes on beside it. Only you can read the file, and a symbolic
    link in its place is refused (see private_write). A log that is in the folder is taken for yours: whoever can
    write to the folder as you can change a log or put one there, and the recorder can't prevent that. Your agent
    may have file tools on the same machine: keep the folder outside its working directories.

    Of the options the file keeps the system prompt, the tools, the two lists of permission rules, the permission
    mode, the model, the limit on turns, the names of the MCP servers and, of each sub-agent's definition, its
    description, prompt, tools, disallowed tools, model and permission mode. It also notes whether a permission
    callback and hooks were set, by name. It never keeps env, settings, extra_args or any MCP server's settings.
    Of each message it keeps what the review reads: all of what the agent wrote and every tool result, the ids,
    and of the SDK's own messages the fields named in INIT_FIELDS, DENIED_FIELDS and RESULT_FIELDS. So the file
    holds whatever the agent read and wrote, and your system prompt and permission rules as you wrote them; any of
    these can hold a secret.

    Nothing is imported from the Agent SDK. From TypeScript, write the same file yourself (see REFERENCE.md)."""

    OPTION_FIELDS = (
        "tools",
        "allowed_tools",
        "disallowed_tools",
        "permission_mode",
        "model",
        "max_turns",
    )
    HOOKS = (
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "UserPromptSubmit",
        "Stop",
        "SubagentStop",
        "PreCompact",
        "Notification",
        "SubagentStart",
        "PermissionRequest",
    )
    BLOCKS = {
        "TextBlock": ("text", ("text",)),
        "ThinkingBlock": ("thinking", ("thinking",)),
        "ToolUseBlock": ("tool_use", ("id", "name", "input")),
        "ToolResultBlock": ("tool_result", ("tool_use_id", "content", "is_error")),
        "ServerToolUseBlock": ("server_tool_use", ("id", "name", "input")),
        "ServerToolResultBlock": ("server_tool_result", ("tool_use_id", "content")),
    }
    INIT_FIELDS = (
        "session_id",
        "claude_code_version",
        "tools",
        "agents",
        "permissionMode",
        "model",
    )
    DENIED_FIELDS = ("session_id", "tool_use_id", "tool_name", "decision_reason_type", "agent_id")
    RESULT_FIELDS = (
        "subtype",
        "is_error",
        "num_turns",
        "session_id",
        "stop_reason",
        "api_error_status",
        "duration_ms",
    )
    LEFT_OUT = (
        "stream_event",
        "rate_limit_event",
    )  # partial messages and rate limits are no part of the record
    MOST_FILES = (
        1000  # how many files beside one another may share a name before the recorder gives up
    )

    def __init__(self, agent, folder, options=None, session_id=None, agent_version=None):
        if session_id is not None and not isinstance(session_id, str):
            raise TypeError(
                f"session_id should be text, and is {kind_of_value(session_id)}: pass it as str(…), or leave it "
                "out to use the id that the SDK reports."
            )
        if session_id is not None and id_problem(session_id):
            raise ValueError("session_id: " + id_problem(session_id))
        self.folder, self.path, self._wrote = Path(folder), None, None
        # Whether your own options say that this session continues another. Only then is an earlier log taken up.
        # A session that forks gets a new id, so it has no earlier log of its own.
        asks = (
            bool(self._of(options, "resume")) or self._of(options, "continue_conversation") is True
        )
        self._continues = asks and self._of(options, "fork_session") is not True
        self._recorder = {
            "sdk_version": self._sdk_version(),
            "cli_version": None,
            "permission_callback": self._of(options, "can_use_tool") is not None,
            "approvals_recorded": False,
            "hooks": [h for h in self.HOOKS if h in (self._of(options, "hooks") or {})],
            "forward_subagent_text": self._of(options, "forward_subagent_text") is True,
            "continues": self._continues,
        }
        self.log = {
            "log_format": "agent_sdk_messages",
            "session_id": None,
            "agent": agent,
            **({"agent_version": str(agent_version)} if agent_version is not None else {}),
            "started_at": None,
            "ended_at": None,
            "recorder": self._recorder,
            "options": self._kept(options),
            "entries": [],
        }
        private_dir(self.folder)
        if session_id is not None:
            self._named(session_id)

    @staticmethod
    def _of(thing, name):
        return thing.get(name) if isinstance(thing, dict) else getattr(thing, name, None)

    @staticmethod
    def _sdk_version():
        try:
            from importlib.metadata import version

            return version("claude-agent-sdk")
        except Exception:  # not installed under that name, or no metadata: the file says null
            return None

    @staticmethod
    def _json(value):
        """A value as plain JSON: an object of a class is written as its fields, anything else as its text."""
        return json.loads(
            json.dumps(value, default=lambda o: getattr(o, "__dict__", None) or str(o))
        )

    def _kept(self, options):
        """The fixed list of what the file keeps of the options' settings."""
        if options is None:
            return {}
        kept = {name: self._json(self._of(options, name)) for name in self.OPTION_FIELDS}
        if isinstance(kept["tools"], dict):  # the preset of tools: its name alone
            kept["tools"] = {"preset": kept["tools"].get("preset")}
        prompt = self._of(options, "system_prompt")
        if isinstance(
            prompt, dict
        ):  # a preset, or a file that the recorder does not read: what you appended alone
            prompt = {"preset": prompt.get("preset"), "append": prompt.get("append") or ""}
        kept["system_prompt"] = self._json(prompt)
        servers = self._of(options, "mcp_servers")
        kept["mcp_servers"] = (
            sorted(str(name) for name in servers) if isinstance(servers, dict) else []
        )
        kept["agents"] = {
            str(name): {
                field: self._json(self._of(definition, field))
                for field in AGENT_SDK_DEFINITION_FIELDS
                if self._of(definition, field) is not None
            }
            for name, definition in (self._of(options, "agents") or {}).items()
        }
        return kept

    @staticmethod
    def _now():
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _read(path):
        """The log that is at this path, or None if what is there is no JSON object that you own. A link is not
        followed and a pipe is not waited for."""
        careful = getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            fd = os.open(path, os.O_RDONLY | careful)
        except OSError:
            return None
        try:
            found = os.fstat(fd)
            if not stat.S_ISREG(found.st_mode) or (
                hasattr(os, "getuid") and os.getuid() != found.st_uid
            ):
                return None
            with os.fdopen(os.dup(fd), "r", encoding="utf-8", errors="backslashreplace") as handle:
                held = json.loads(handle.read())
            return held if isinstance(held, dict) else None
        except (OSError, ValueError, RecursionError):
            return None
        finally:
            os.close(fd)

    def _named(self, session_id):
        """Name the file, once the session's id is known, and take up the log of the same session if it is there."""
        # An id from the stream that the review could not take: the log gets a plain one in its place.
        if id_problem(session_id):
            reported = session_id if isinstance(session_id, str) else str(session_id)
            self.log["session_id_as_reported"] = reported
            session_id = (
                "session-" + hashlib.sha256(reported.encode("utf-8", "replace")).hexdigest()[:16]
            )
        self.log["session_id"] = session_id
        self._place(take_up=self._continues)

    def _place(self, take_up, moving=False):
        """Choose the file: the first name that is free, or, where your options say that this session continues
        another, the log of this session that is there already. A file that is there and is not taken up is left
        as it is, and the log's recorder block says that the log was written beside one (unless _write is moving
        the log away from a file that another writer changed). What is at the chosen path at this moment is
        remembered, so that the first write can tell whether another writer has written there since."""
        session_id = self.log["session_id"]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", session_id)
        for n in range(1, self.MOST_FILES + 1):
            path = self.folder / (name + ("" if n == 1 else f"-{n}") + ".json")
            if not os.path.lexists(path):
                self.path, self._wrote = path, self.ABSENT
                return
            if not moving:
                self._recorder["beside"] = True
            before = self._seen(path)
            held = self._read(path) if take_up else None
            mine = (
                held is not None
                and held.get("log_format") == "agent_sdk_messages"
                and held.get("session_id") == session_id
                and isinstance(held.get("entries"), list)
            )
            if mine:  # this session's own log, from an earlier run of your code: go on after it
                self._recorder.pop("beside", None)
                again = {
                    "at": self._now(),
                    "resumed": {"options": self.log["options"], "recorder": self._recorder},
                }
                self.log.update(
                    started_at=held.get("started_at"),
                    recorder=held.get("recorder") if isinstance(held.get("recorder"), dict) else {},
                    options=held.get("options") if isinstance(held.get("options"), dict) else {},
                    entries=[*held["entries"], again, *self.log["entries"]],
                )
                self.path, self._wrote = path, before
                return
        raise ValueError(
            f"{self.folder} holds {self.MOST_FILES} files named after this session's id, and none is its log. "
            "Use another folder."
        )

    def _entry(self, entry):
        now = self._now()
        self.log["started_at"] = self.log["started_at"] or now
        self.log["ended_at"] = now
        self.log["entries"].append({"at": now, **entry})
        # Until the SDK has reported the session's id, entries wait in memory.
        if self.path is not None:
            self._write()

    ABSENT = "absent"  # what _seen gives where nothing is at the path

    @classmethod
    def _seen(cls, path):
        """What tells one state of a file from another: which file it is, its size and when it was changed.
        ABSENT if nothing is there, and None if what is there is no plain file or can't be looked at."""
        try:
            found = os.lstat(path)
        except FileNotFoundError:
            return cls.ABSENT
        except OSError:
            return None
        return (
            (found.st_ino, found.st_size, found.st_mtime_ns)
            if stat.S_ISREG(found.st_mode)
            else None
        )

    def _write(self):
        """Write the log whole. If a plain file is at the path, and which file it is, its size or its time is not
        what this recorder last saw, another writer is taken to have written to it, for example a second
        recorder on the same session: that file is left as it is, this log goes beside it, and the log says so
        (in its recorder block or, for a log that was taken up, in the block of the run that took it up). What
        this recorder last saw is what it last wrote, or, before its first write, what was there when the name
        was chosen or the log was taken up. Two writers that write at the very same moment are not kept apart:
        run one recorder on a session at a time."""
        now = self._seen(self.path)
        if self._wrote is not None and now not in (None, self.ABSENT) and now != self._wrote:
            self._recorder["moved_beside"] = True
            self._place(take_up=False, moving=True)
        private_write(self.path, json.dumps(self.log))
        self._wrote = self._seen(self.path)

    def sent(self, prompt):
        """Log the text of one prompt that your code sends. Call it before you send the prompt."""
        if not isinstance(prompt, str):
            raise TypeError(
                f"sent() takes the text of one prompt, and was given {kind_of_value(prompt)}. With a stream of "
                "prompts, call sent() with each message's text as you yield it."
            )
        self._entry({"sent": prompt})
        return prompt

    def record(self, message):
        """Log one message the SDK gave you: an object of the Python SDK's classes, or a message as JSON."""
        wire = self._wire(message)
        if wire is not None:
            if self.path is None and wire.get("session_id") is not None:
                self._named(wire["session_id"])
            if wire.get("type") == "system" and wire.get("subtype") == "init":
                version = wire.get("claude_code_version")
                self._recorder["cli_version"] = version if isinstance(version, str) else None
            self._entry({"message": wire})
        return message

    def approvals(self, can_use_tool):
        """Your permission callback, wrapped so that each request and its answer is logged. Only an answer that the
        SDK takes for an allow (a PermissionResultAllow) is logged as one; any other answer, and a callback that
        raises, is logged as a deny."""
        self._recorder["approvals_recorded"] = True

        async def recorded(tool_name, tool_input, context):
            decision = "deny"
            try:
                answer = await can_use_tool(tool_name, tool_input, context)
                allow = type(answer).__name__ == "PermissionResultAllow"
                decision = (
                    "allow" if allow and getattr(answer, "behavior", None) == "allow" else "deny"
                )
                return answer
            finally:
                call_id = self._of(context, "tool_use_id")
                call_id = call_id if isinstance(call_id, str) else None
                self._entry({"approval": {"tool_use_id": call_id, "decision": decision}})

        return recorded

    def _block(self, block):
        """What the file keeps of one block: its type, and of a block that the review reads the fields it reads.
        The same is kept of a block of the SDK's classes and of a block given as JSON."""
        if isinstance(block, dict):
            kind = block.get("type")
            if kind == "text":
                names = ("text",)
            elif kind == "thinking":
                names = ("thinking",)
            elif kind in AGENT_SDK_TOOL_USES:
                names = ("id", "name", "input")
            elif isinstance(kind, str) and kind.endswith("tool_result"):
                names = ("tool_use_id", "content", "is_error")
            else:
                names = ()
            return self._json(
                {"type": kind, **{name: block[name] for name in names if name in block}}
            )
        kind, names = self.BLOCKS.get(type(block).__name__, ("unknown", ()))
        return {"type": kind, **{name: self._json(getattr(block, name, None)) for name in names}}

    def _wire(self, message):
        """What the file keeps of a message, in the SDK's wire shape, or None for a partial message or a rate limit
        event, which are no part of the record. The same is kept of an object of the SDK's classes and of a message
        given as JSON."""
        if not isinstance(message, dict):
            name = type(message).__name__
            if hasattr(message, "subtype") and isinstance(getattr(message, "data", None), dict):
                message = dict(message.data)  # a system message: the SDK holds its wire form
            elif name in ("AssistantMessage", "UserMessage"):
                role = "assistant" if name == "AssistantMessage" else "user"
                inner = {"role": role, "content": message.content}
                if role == "assistant":
                    inner.update(
                        id=getattr(message, "message_id", None),
                        model=getattr(message, "model", None),
                        stop_reason=getattr(message, "stop_reason", None),
                    )
                fields = ("parent_tool_use_id", "uuid", "error", "session_id", "origin")
                message = {
                    "type": role,
                    "message": inner,
                    **{f: getattr(message, f, None) for f in fields},
                }
            elif name == "ResultMessage":
                fields = (*self.RESULT_FIELDS, "permission_denials", "errors")
                message = {"type": "result", **{f: getattr(message, f, None) for f in fields}}
            elif name in ("StreamEvent", "RateLimitEvent"):
                return None
            else:
                message = {"type": "unknown"}
        kind, subtype = message.get("type"), message.get("subtype")
        if kind in self.LEFT_OUT:
            return None
        if kind in ("assistant", "user"):
            inner = message.get("message") if isinstance(message.get("message"), dict) else {}
            content = inner.get("content")
            if not isinstance(content, str):
                content = (
                    [self._block(b) for b in content or []]
                    if isinstance(content, (list, tuple))
                    else []
                )
            kept = {"type": kind, "message": {"role": inner.get("role", kind), "content": content}}
            for field in ("id", "model", "stop_reason", "stop_details"):
                if kind == "assistant" and inner.get(field) is not None:
                    kept["message"][field] = inner[field]
            for field in (
                "parent_tool_use_id",
                "uuid",
                "session_id",
                "error",
                "isReplay",
                "isSynthetic",
            ):
                if message.get(field) is not None:
                    kept[field] = message[field]
            origin = message.get("origin")
            origin = origin if isinstance(origin, dict) else getattr(origin, "__dict__", None)
            if isinstance(origin, dict):
                kept["origin"] = {"kind": origin.get("kind")}
            return self._json(kept)
        if kind == "result":
            kept = {
                "type": "result",
                **{f: message[f] for f in self.RESULT_FIELDS if message.get(f) is not None},
            }
            denials = message.get("permission_denials")
            kept["permission_denials"] = [
                {"tool_name": self._of(d, "tool_name"), "tool_use_id": self._of(d, "tool_use_id")}
                for d in (denials if isinstance(denials, (list, tuple)) else [])
            ]
            errors = message.get("errors")
            # A result's error strings are counted, not kept.
            kept["errors"] = len(errors) if isinstance(errors, (list, tuple)) else 0
            return self._json(kept)
        if kind == "system" and subtype == "init":
            kept = {"type": kind, "subtype": subtype}
            kept.update({f: message[f] for f in self.INIT_FIELDS if message.get(f) is not None})
            servers = message.get("mcp_servers")
            kept["mcp_servers"] = [
                {"name": self._of(s, "name")}
                for s in (servers if isinstance(servers, (list, tuple)) else [])
            ]
            return self._json(kept)
        if kind == "system" and subtype == "permission_denied":
            kept = {"type": kind, "subtype": subtype}
            kept.update({f: message[f] for f in self.DENIED_FIELDS if message.get(f) is not None})
            return self._json(kept)
        # Any other message: that there was one, and of what kind. The converter counts these in a note.
        return self._json({"type": kind, **({"subtype": subtype} if subtype is not None else {})})


def default_audit_dir():
    """Where the audit trail goes unless LOG_REVIEW_AUDIT_DIR says otherwise: a cache folder under your home
    directory, outside any repository, since it holds whole transcripts and any secrets the agents saw."""
    return Path(
        os.getenv("LOG_REVIEW_AUDIT_DIR") or Path.home() / ".cache" / "agent_log_review" / "audit"
    )


def my_logs_dir(name):
    """The folder for the logs of your own agent: under your home directory, beside the audit trail and outside
    any repository, since logs hold whole transcripts. Nothing is created by asking: collect_managed_agents
    makes the folder (see logs_dir). Where no home directory can be found, a RuntimeError says so; there is no
    other folder that the helper could choose safely for you."""
    try:
        return Path.home() / ".cache" / "agent_log_review" / "logs" / name
    except RuntimeError as why:
        raise RuntimeError(
            f"No home directory was found, so the helper has no folder of your own for the logs of {name}. "
            "Give collect_managed_agents a folder of your own."
        ) from why


def new_audit_dir():
    """This run's audit folder, not yet created: LOG_REVIEW_AUDIT_DIR as it is if you set it, otherwise a new
    time-stamped folder under default_audit_dir(), so a run never overwrites an earlier run's trail."""
    if os.getenv("LOG_REVIEW_AUDIT_DIR"):
        return default_audit_dir()
    return default_audit_dir() / datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def display_path(path):
    """A folder as it is fine to print: under your home directory as ~/..., otherwise the name of the setting that
    chose it, so a run on a server doesn't print that server's paths."""
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return "the folder named in LOG_REVIEW_AUDIT_DIR"


# --- What the notebook's rules call: depth guards, strings, and hosts and recipients in a call ---


def safe_code(reason):
    """A reason code as it may go into a step's task: itself if it is a short code, otherwise "other"."""
    return reason if isinstance(reason, str) and SAFE_CODE.fullmatch(reason) else "other"


def plain_values(value):
    """Every value inside a value that is neither a dict nor a list, in the order in which strings() would meet
    them. It walks with a list of its own and never calls itself, so no nesting is too deep for it."""
    found, to_do = [], [value]
    while to_do:
        x = to_do.pop()
        if isinstance(x, dict):
            to_do.extend(reversed(list(x.values())))
        elif isinstance(x, list):
            to_do.extend(reversed(x))
        else:
            found.append(x)
    return found


def deeper_than(value, limit):
    """Whether a dict or a list in the value lies limit levels deep or deeper. It never calls itself."""
    to_do = [(value, 0)]
    while to_do:
        x, depth = to_do.pop()
        if isinstance(x, (dict, list)):
            if depth >= limit:
                return True
            to_do.extend((v, depth + 1) for v in (x.values() if isinstance(x, dict) else x))
    return False


def not_too_deep(value, limit=MAX_DEPTH):
    """(the value, whether any of it was too deep). A dict or a list that lies limit levels deep or deeper is
    replaced by a list of its plain values (see plain_values): the values are the same, in the same order, and
    the names of their fields are gone. Everything above it is copied as it is. It never calls itself."""
    too_deep, top = False, [None]
    # Each entry: a value, the dict or list it goes into, its place there, and its depth.
    to_do = [(value, top, 0, 0)]
    while to_do:
        x, into, place, depth = to_do.pop()
        if isinstance(x, (dict, list)) and depth >= limit:
            into[place], too_deep = plain_values(x), True
        elif isinstance(x, dict):
            copy = into[place] = dict.fromkeys(x)
            to_do.extend((v, copy, k, depth + 1) for k, v in x.items())
        elif isinstance(x, list):
            copy = into[place] = [None] * len(x)
            to_do.extend((v, copy, n, depth + 1) for n, v in enumerate(x))
        else:
            into[place] = x
    return top[0], too_deep


def strings(x):
    """Every decoded string inside a value, so rules see real quotes and newlines, not JSON escapes."""
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def fields(ev):
    """Map a normalized event to the rule file's applies_to names."""
    if ev["source"] == "agent" and ev["kind"] == "tool_call":
        return {"command": list(strings(ev.get("input", {})))}
    if ev["source"] == "agent":
        return {"prose": list(strings(ev.get("content")))}
    if ev["source"] == "tool_result":
        return {"output": list(strings(ev.get("content")))}
    return {}


class OutOfTime:
    """What a search gives once the session's time has run out. It is false, like "no match", and it is not None,
    which stands for one rule that was stopped or not run. Test for it with getattr(x, "out_of_time", False)
    where the Rules object may be older than the module, as after importlib.reload."""

    out_of_time = True

    def __bool__(self):
        return False

    def __repr__(self):
        return "OUT_OF_TIME"


class Rules:
    """The pattern rule files: {"rules": [{id, description, category, applies_to, regex}, ...]}.

    applies_to is "command" (what the agent ran), "output" (what tools returned) or "any"; regex flags go inline,
    such as (?i). A rule with "context_only": true points the reviewer at events but never picks a session alone.
    Files are checked on load: every field present, ids unique across files and none of OWN_HITS, "context_only"
    true or false if it is given, patterns that compile.
    Patterns run in your process, and a pattern with nested quantifiers, such as (a+)+$, can take exponential time,
    even on a short text. So the rules are bounded three ways. Each text is cut to MAX_RULE_TEXT characters. Each
    search (one rule on one text) is stopped after search_timeout_s seconds, with a warning that names the rule.
    And the rules on one session are stopped once session_timeout_s seconds have passed. Still, keep patterns
    simple and try them on long outputs. hits() gives the event of a longer text a "text-too-long" hit, the
    event where a rule was stopped a "rule-timeout" hit, and the event where the session's time ran out a
    "rules-out-of-time" hit; each sends the session to review.
    Patterns are compiled with the third-party regex package, which takes the same syntax as re and can stop a
    search after a number of seconds on every operating system and in any thread. With search_timeout_s of 0 or
    None, hits() does not run the pattern rules and gives each session a "rules-not-run" hit, which sends it to
    review. accept_searches_that_may_never_end=True runs them then with no stop. search_timeout_s is 0, None, or a number of seconds from 0.01 to 3,600; session_timeout_s is a
    number of seconds from 0.01 to 86,400."""

    APPLIES_TO = ("command", "output", "any")
    MAX_RULE_TEXT = 100_000
    TIMEOUT = "rule-timeout"
    RULES_OUT_OF_TIME = "rules-out-of-time"  # the rules' time for one session is over
    TOO_LONG = "text-too-long"
    TOO_DEEP = "nested-too-deep"
    NOT_RUN = "rules-not-run"
    OWN_HITS = (
        TIMEOUT,
        RULES_OUT_OF_TIME,
        TOO_LONG,
        TOO_DEEP,
        NOT_RUN,
    )  # the helper's own names for a hit: never a rule's id, never context only
    OUT_OF_TIME = OutOfTime()
    SHORTEST_TIMER_S = (
        0.01  # with less than this left of a session's time, its time is taken as over
    )

    def __init__(
        self,
        rule_files,
        search_timeout_s=30.0,
        accept_searches_that_may_never_end=False,
        session_timeout_s=120.0,
    ):
        self.rules, self.source, self.search_timeout_s, self.timed_out = (
            [],
            {},
            search_timeout_s,
            set(),
        )
        self.unstopped = accept_searches_that_may_never_end
        self.session_timeout_s = session_timeout_s
        self.began, self.out_of_time = None, False  # of the current session: see hits() and _left()
        limit = search_timeout_s
        if limit is not None and (
            isinstance(limit, bool)
            or not isinstance(limit, (int, float))
            or not (limit == 0 or 0.01 <= limit <= 3600)
        ):
            given = one_line(repr(limit))
            given = given if len(given) <= 40 else given[:40] + " ..."
            raise ValueError(
                "search_timeout_s must be an int or a float, from 0.01 to 3,600, "
                f"or 0 or None for no limit; it is {given}"
            )
        limit = session_timeout_s
        if (
            isinstance(limit, bool)
            or not isinstance(limit, (int, float))
            or not 0.01 <= limit <= 86400
        ):
            given = one_line(repr(limit))
            given = given if len(given) <= 40 else given[:40] + " ..."
            raise ValueError(
                "session_timeout_s must be a number of seconds, an int or a float from 0.01 to 86,400 "
                f"(it has no setting for no limit); it is {given}"
            )
        for path in rule_files:
            path = Path(path)
            try:
                rules = json.loads(path.read_text())["rules"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise ValueError(
                    f'{path.name}: expected {{"rules": [...]}} ({type(exc).__name__}: {exc})'
                ) from exc
            for n, r in enumerate(rules, 1):
                self._check(path, n, r)
                self.rules.append(r)
                self.source[r["id"]] = path.name
        self.compiled = {}
        for r in self.rules:
            try:
                self.compiled[r["id"]] = regex.compile(r["regex"])
            except regex.error as exc:
                raise ValueError(
                    f'{self.source[r["id"]]}: rule "{r["id"]}": the regex does not compile: {exc}'
                ) from exc
        self.context_only = {r["id"] for r in self.rules if r.get("context_only") is True}
        self.said_too_long = self.said_not_run = self.said_out_of_time = False

    def _check(self, path, n, r):
        where = f"{path.name}: rule {n}" + (
            f' ("{r["id"]}")' if isinstance(r, dict) and "id" in r else ""
        )
        if not isinstance(r, dict):
            raise ValueError(f"{where}: each rule must be an object")
        for key in ("id", "regex", "applies_to", "category"):
            if not isinstance(r.get(key), str) or not r[key]:
                raise ValueError(
                    f'{where}: missing "{key}" (a rule needs id, regex, applies_to and category)'
                )
        if r["applies_to"] not in self.APPLIES_TO:
            raise ValueError(
                f'{where}: applies_to "{r["applies_to"]}" must be one of {", ".join(self.APPLIES_TO)}'
            )
        if r["id"] in self.source:
            raise ValueError(
                f'{where}: the id "{r["id"]}" is already used in {self.source[r["id"]]}'
            )
        if r["id"] in self.OWN_HITS:
            raise ValueError(
                f'{where}: the id "{r["id"]}" is one of the helper\'s own names for a hit '
                f"({', '.join(self.OWN_HITS)}); give the rule another id"
            )
        if "context_only" in r and not isinstance(r["context_only"], bool):
            given = one_line(json.dumps(r["context_only"]))
            given = given if len(given) <= 40 else given[:40] + " ..."
            raise ValueError(
                f'{where}: "context_only" must be true or false, without quotes; it is {given}'
            )

    @staticmethod
    def stopped_words(rule_id):
        """The category of a "rule-timeout" hit: which rule was stopped, and that it was then left out."""
        return f"timeout: {rule_id}; this rule was not run on the later events of this session"

    def why_no_stop(self):
        """Why a search can't be stopped here, and what to do about it, as (why, what to do); None where it can."""
        if not self.search_timeout_s:
            return (
                "search_timeout_s is set to no limit",
                "give search_timeout_s a number of seconds above 0",
            )
        return None

    @staticmethod
    def out_of_time_words(in_the_refusal_search=False):
        """The category of a "rules-out-of-time" hit: where the session's time ran out, and what may be missed."""
        if in_the_refusal_search:
            return (
                "timeout: the pattern rules' time for this session, session_timeout_s, ran out at this event, in "
                "the search for refusals; retry-after-refusal and refusal-after-outbound-attempt may have "
                "missed a refusal from this event on"
            )
        return (
            "timeout: the pattern rules' time for this session, session_timeout_s, ran out at this event; some "
            "pattern rules were not run on it or on the events after it, and retry-after-refusal and "
            "refusal-after-outbound-attempt may have missed a refusal anywhere in the session"
        )

    def _search(self, rule_id, text):
        """True or False for whether the rule matches text; None if the search took over search_timeout_s, or if it
        was not run because it couldn't have been stopped (see why_no_stop); OUT_OF_TIME, which is false too, once
        session_timeout_s seconds have passed since the rules began on the current session. hits() starts a
        session's time, and it runs on by the clock until the next hits()."""
        text = text[: self.MAX_RULE_TEXT]
        left = self._left()
        if self.out_of_time or left < self.SHORTEST_TIMER_S:
            return self._ran_out()
        if self.why_no_stop():
            # With no stop, the session's time is looked at only between two searches.
            return (self.compiled[rule_id].search(text) is not None) if self.unstopped else None

        timer = min(self.search_timeout_s, left)
        try:
            return self.compiled[rule_id].search(text, timeout=timer) is not None
        except TimeoutError:
            if timer < self.search_timeout_s:
                # It was the session's time that ran out, not the rule's own.
                return self._ran_out()
            if rule_id not in self.timed_out:
                self.timed_out.add(rule_id)
                print(
                    f'Rule "{rule_id}" ({self.source[rule_id]}) took over {self.search_timeout_s:g} s on one text '
                    'and was stopped. Simplify its pattern. A session where it times out gets a "rule-timeout" hit, '
                    "which sends it to review, because the rule couldn't judge that text. The rule is not run on "
                    "the later events of that session."
                )
            return None

    def matches(self, rule_id, text):
        """Whether the rule matches text, through the same bounded search as hits(): False where the search was
        stopped, not run, or the session's time was over (see _search)."""
        return bool(self._search(rule_id, text))

    def _left(self):
        """The seconds that are left of the current session's time. Its time starts where hits() begins, or at
        the first search where there was no hits() before it."""
        if self.began is None:
            self.began = time.monotonic()
        return self.session_timeout_s - (time.monotonic() - self.began)

    def _too_deep(self, record):
        """One "nested-too-deep" hit for each event that the record lists in "too_deep", or one for the event
        that it names in "too_deep_elsewhere"."""
        here = (
            f"too deep: this event is nested over {MAX_DEPTH} levels deep; below {MAX_DEPTH} levels its values "
            "were kept and the names of their fields were dropped, so a rule that goes by a field's name may "
            "have missed something. No honest log is nested so deep"
        )
        elsewhere = (
            f"too deep: a part of this session's log, in this event or outside it, is nested over {MAX_DEPTH} "
            "levels deep, counted from the top of the file; if it lies in a tool's result or in a message, "
            f"the names of its fields below {MAX_DEPTH} levels may have been dropped, so the rules and the "
            "reviewer may not have read those names. No honest log is nested so deep"
        )
        hits = [
            {"rule": self.TOO_DEEP, "category": here, "event": i}
            for i in record.get("too_deep", ())
        ]
        if "too_deep_elsewhere" in record:
            hits.append(
                {
                    "rule": self.TOO_DEEP,
                    "category": elsewhere,
                    "event": record["too_deep_elsewhere"],
                }
            )
        return hits

    def _ran_out(self):
        self.out_of_time = True
        if not self.said_out_of_time:
            self.said_out_of_time = True
            print(
                f"The pattern rules took over {self.session_timeout_s:g} s on a session and were stopped "
                f'there. Each such session gets a "{self.RULES_OUT_OF_TIME}" hit, which sends it to review, '
                "because the rules didn't read all of it; the table of flagged sessions shows which. The "
                "rules go on with the next session. If your sessions are long and honest, give "
                "session_timeout_s (SESSION_TIMEOUT_S in the notebook) more seconds."
            )
        return self.OUT_OF_TIME

    def hits(self, record):
        """Every rule that matches an event, as {"rule", "category", "event"}. A rule that takes too long on an
        event's text (see search_timeout_s) couldn't judge it: that is a "rule-timeout" hit, with the rule named at
        the start of its category ("timeout: <rule id>; ..."), so the session goes to review instead of passing
        unexamined; the rule is then left out for the rest of the session. Once session_timeout_s seconds have
        passed since hits() began, the event then being searched gets one "rules-out-of-time" hit and no rule is
        run on the rest of the session. A text that is longer than MAX_RULE_TEXT gives its event one
        "text-too-long" hit, also once the session's time is over, and an event that was nested too deep one
        "nested-too-deep" hit, also where no rule is run. Where a search can't be stopped (see why_no_stop), no
        rule is run and the session's first event gets one "rules-not-run" hit. None of the five can be made
        context only."""
        self.began, self.out_of_time = time.monotonic(), False
        no_stop = None if self.unstopped else self.why_no_stop()
        if no_stop:
            why, to_do = no_stop
            if not self.said_not_run:
                self.said_not_run = True
                print(
                    f"The pattern rules were not run: {why}, so a slow pattern could not be stopped and could "
                    f'run for hours. Every session gets a "{self.NOT_RUN}" hit and goes to review. To run the '
                    f"rules, {to_do}, or pass accept_searches_that_may_never_end=True to run them with no stop."
                )
            not_run = f"not run: {why}, so no pattern rule was run on this session"
            first = record["events"][:1]
            return self._too_deep(record) + [
                {"rule": self.NOT_RUN, "category": not_run, "event": ev["i"]} for ev in first
            ]
        hits, uncut, stopped = self._too_deep(record), record.get("uncut", {}), set()
        for ev in record["events"]:
            timed_out, too_long, ran_out = set(), False, False
            whole = uncut.get(str(ev["i"]))
            for where, texts in fields(ev).items():
                if whole is not None and where == "output":
                    # A tool result that was cut for the reviewer. The rules read the whole of it, up to
                    # MAX_RULE_TEXT, and then the cut text too, which holds the end of a longer result.
                    texts = [whole, *texts]
                too_long = too_long or any(len(t) > self.MAX_RULE_TEXT for t in texts)
                for r in self.rules:
                    if self.out_of_time:
                        break
                    if r["applies_to"] not in (where, "any") or r["id"] in stopped:
                        continue
                    for t in texts:
                        found = self._search(r["id"], t)
                        if found is self.OUT_OF_TIME:
                            ran_out = True
                            break
                        if found is None:
                            timed_out.add(r["id"])
                            stopped.add(r["id"])
                            break
                        if found:
                            hits.append(
                                {"rule": r["id"], "category": r["category"], "event": ev["i"]}
                            )
                            break
            for rule_id in sorted(timed_out):
                hits.append(
                    {
                        "rule": self.TIMEOUT,
                        "category": self.stopped_words(rule_id),
                        "event": ev["i"],
                    }
                )
            if ran_out:
                hits.append(
                    {
                        "rule": self.RULES_OUT_OF_TIME,
                        "category": self.out_of_time_words(),
                        "event": ev["i"],
                    }
                )
            if too_long:
                n = f"{self.MAX_RULE_TEXT:,}"
                if not self.said_too_long:
                    self.said_too_long = True
                    print(
                        f"The pattern rules read only the first {n} characters of a text. A session with a "
                        f'longer text gets a "{self.TOO_LONG}" hit, which sends it to review, because the rules '
                        "couldn't read all of it."
                    )
                read = (
                    f"too long: a text of this event has over {n} characters, "
                    "and the pattern rules did not read all of it"
                )
                hits.append({"rule": self.TOO_LONG, "category": read, "event": ev["i"]})
        return hits


# A URL with any scheme (http, https, wss, ftp, s3, tcp, ...), in any case, with optional user:password@ in front of the
# host. The host is captured without the user info, so https://allowed.example@evil.example is read as evil.example.
URL_HOST = re.compile(
    r"(?i)\b[a-z][a-z0-9+.-]{0,31}://(?:[^\s/@?#]*@)?(\[[0-9a-f:.]{2,45}\]|[a-z0-9.\-]{1,253})"
)
# A credential named in a call: an UPPER_CASE name ending in TOKEN, SECRET, PASSWORD, PASSWD, API_KEY, APIKEY,
# ACCESS_KEY, PRIVATE_KEY, AUTH_KEY or _PAT. It does not see lower-case names, names of other shapes (DB_URL,
# STRIPE_KEY), or a secret pasted into a command as a value. Names that are pagination or CSRF tokens are skipped.
SECRET_NAME = re.compile(
    r"\b[A-Z][A-Z0-9_]{0,60}(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|ACCESS_KEY|PRIVATE_KEY|AUTH_KEY|_PAT)\b"
)
BENIGN_SECRET_NAME = re.compile(
    r"(?:^|_)(?:NEXT|PAGE|PAGINATION|CONTINUATION|CURSOR|CSRF|XSRF)(?:_|$)"
)
# The structural rules, for a grant's "context_only_rules": a rule listed there points the reviewer at events
# but doesn't pick a session alone.
STRUCTURAL_RULES = (
    "destination-not-in-grant",
    "ip-literal-url",
    "recipient-not-in-grant",
    "credential-not-granted",
    "credential-away-from-home",
    "refusal-after-outbound-attempt",
    "retry-after-refusal",
)
# Fields that hold a file's body or a message's text: links in them are not destinations the call reaches.
BODY_KEYS = {"content", "file_text", "old_str", "new_str", "text", "message", "body"}
# Shell commands that name a destination, and what their bare host arguments look like.
SHELL_DESTINATION = re.compile(r"\b(curl|wget|nc|ncat|ssh|scp|dig|nslookup|host)\b([^\n|;&<>]*)")
HOST_FIRST_COMMANDS = {
    "nc",
    "ncat",
    "ssh",
    "scp",
    "dig",
    "nslookup",
    "host",
}  # their words are hosts, not files
AMBIGUOUS_EXTENSIONS = {
    "sh",
    "py",
    "md",
    "rs",
    "zip",
}  # file extensions that are also top-level domains
BARE_HOST = re.compile(
    r"(?:[\w.-]+@)?((?:\d{1,3}\.){3}\d{1,3}|[a-z0-9-]+(?:\.[a-z0-9-]+)+)(?::[^\s]*)?"
)
FILE_EXTENSIONS = {
    "txt", "csv", "tsv", "json", "jsonl", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "env", "log",
    "md", "html", "htm", "css", "js", "ts", "py", "sh", "rb", "go", "rs", "java", "c", "h", "cpp", "sql",
    "pdf", "png", "jpg", "jpeg", "gif", "svg", "zip", "tar", "gz", "tgz", "bz2", "xz", "bin", "out", "tmp", "bak",
    "pem", "key", "crt", "cer", "lock", "db", "sqlite", "parquet", "xlsx", "docx",
}  # fmt: skip
EMAIL = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
)  # matched against one word at a time, so long text stays fast
EMAIL_WORD_BREAK = re.compile(r"[\s<>,;\"'()\[\]]+")


def host_allowed(host, allowed):
    return any(host == a or host.endswith("." + a) for a in allowed)


def normalize_host(host):
    """A host as the rules compare it: lower case, no brackets, no trailing dot, and an IPv4-mapped IPv6 address
    ([::ffff:1.2.3.4]) as the IPv4 address it stands for."""
    host = host.lower().strip("[]").rstrip(".")
    mapped = re.fullmatch(r"::ffff:(\d{1,3}(?:\.\d{1,3}){3})", host)
    return mapped.group(1) if mapped else host


def is_ip(host):
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def is_loopback(host):
    """The machine the agent runs on: never a destination outside the grant."""
    host = normalize_host(host)
    if host in ("localhost", "0.0.0.0"):  # noqa: S104 (it names the machine; nothing is bound to it)
        return True
    try:
        return ipaddress.ip_address(
            host
        ).is_loopback  # 127.0.0.0/8 and ::1, and nothing that only looks like them
    except ValueError:
        return False  # a name, such as 127.0.0.1.example.com or app.localhost: judged like any other host


def reach_strings(value):
    """Every string in a tool input at any depth, except the text of file bodies and messages: a string held by a
    field in BODY_KEYS. A dict or list held by one (an envelope such as {"message": {"to": ...}}) is still read."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if not (key in BODY_KEYS and isinstance(item, str)):
                yield from reach_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from reach_strings(item)


def shell_hosts(text):
    """Bare hosts that shell commands name: curl -T file host, nc host 443, wget host/path, ssh user@host. A word that
    looks like a file name (out.txt, m.csv) or a path is not a host. The trade-off: a word ending .sh, .py, .md, .rs
    or .zip, which are also domains, is a host after nc, ssh, scp, dig, nslookup or host, but after curl or wget it is
    read as a file unless it has three or more labels (a.b.sh)."""
    for command in SHELL_DESTINATION.finditer(text):
        for word in command.group(2).split():
            word = word.strip("'\"").lower()
            if (
                not word
                or word.startswith(("-", "/", "./", "~", "$"))
                or "://" in word
                or "=" in word
            ):
                continue
            match = BARE_HOST.fullmatch(word.split("/")[0])
            if not match:
                continue
            host = match.group(1)
            if re.fullmatch(
                r"[\d.]+", host
            ):  # an IPv4 address; a decimal such as 4120.00 is not one
                if host.count(".") == 3 and all(int(part) <= 255 for part in host.split(".")):
                    yield host
            else:
                ext = host.rsplit(".", 1)[1]
                file_like = ext in FILE_EXTENSIONS and not (
                    ext in AMBIGUOUS_EXTENSIONS
                    and (command.group(1) in HOST_FIRST_COMMANDS or host.count(".") >= 2)
                )
                if ext.isalpha() and len(ext) > 1 and not file_like:
                    yield host


# Field names whose string value is a host, with or without a scheme, whatever the tool: endpoint, host, url, ...
HOST_KEYS = {
    "endpoint",
    "host",
    "hostname",
    "url",
    "uri",
    "server",
    "domain",
    "base_url",
    "address",
}
HOST_KEY_SUFFIXES = (
    "_url",
    "_uri",
    "_host",
    "_hostname",
    "_endpoint",
    "_domain",
    "_server",
    "_address",
    "_ip",
)
HOST_VALUE = re.compile(
    r"(?:\[[0-9a-f:.]{2,45}\]|(?:\d{1,3}\.){3}\d{1,3}|[a-z0-9-]+(?:\.[a-z0-9-]+)+|localhost)(?::\d+)?(?:/.*)?"
)


def key_hosts(value, key=None):
    """Hosts held in fields named like HOST_KEYS (or ending _url, _host, ...): a bare host, host:port or host/path.
    A value with a scheme, an @ or a space is left to the other readers (URLs, email addresses, shell commands)."""
    if isinstance(value, dict):
        for name, item in value.items():
            if not (name in BODY_KEYS and isinstance(item, str)):
                yield from key_hosts(item, name)
    elif isinstance(value, list):
        for item in value:
            yield from key_hosts(item, key)
    elif (
        isinstance(value, str)
        and key
        and (key.lower() in HOST_KEYS or key.lower().endswith(HOST_KEY_SUFFIXES))
    ):
        text = value.strip().lower()
        if "://" in text or "@" in text or " " in text or not HOST_VALUE.fullmatch(text):
            return
        host = text.split("/")[0]
        if host.startswith("["):
            host = host[: host.index("]") + 1]
        elif host.count(":") == 1:
            host = host.split(":")[0]
        name = normalize_host(host)
        if is_ip(name) or name == "localhost" or name.rsplit(".", 1)[-1] not in FILE_EXTENSIONS:
            yield host


def call_hosts(call, ignored=()):
    """The hosts a tool call reaches, normalized (see normalize_host): URLs of any scheme anywhere in its input except
    file bodies (the host after any user@), bare hosts in shell commands, and the value of a field named like
    HOST_KEYS. Loopback hosts and the grant's ignore_hosts are left out."""
    texts = list(reach_strings(call["input"]))
    found = (
        {h for t in texts for h in URL_HOST.findall(t)}
        | {h for t in texts for h in shell_hosts(t)}
        | set(key_hosts(call["input"]))
    )
    hosts = {normalize_host(h) for h in found}
    return {h for h in hosts if h and not is_loopback(h) and not host_allowed(h, ignored)}


def allowed_recipients(record, grant):
    """Fixed addresses from the grant (an entry such as "@example.com" allows everyone at that domain), plus any
    taken from a tool's result, such as the customer who opened a ticket: {"tool": "get_ticket", "field": "from"}."""
    allowed = [a.lower() for a in grant.get("allowed_recipients", [])]
    source = grant.get("recipient_from_tool_result")
    if source:
        calls = {e.get("call_id"): e["tool"] for e in record["events"] if e["kind"] == "tool_call"}
        for ev in record["events"]:
            # A message from another agent is a result with no call of its own, so it has no call_id.
            of_this_tool = (
                ev.get("call_id") is not None and calls.get(ev["call_id"]) == source["tool"]
            )
            if ev["source"] == "tool_result" and of_this_tool:
                # A result that is not JSON, is not an object, or is nested too deep to be parsed names no
                # recipient.
                with contextlib.suppress(ValueError, AttributeError, TypeError, RecursionError):
                    allowed.append(str(json.loads(ev["content"]).get(source["field"], "")).lower())
    return allowed


def is_recipient_key(key):
    """A field that holds who a message goes to: its name has mail, recipient or address in it, or is or starts or ends
    with to, cc or bcc (to, to_address, send_to, cc_list, bcc)."""
    key = key.lower()
    if "sender" in key or re.search(
        r"(?:^|_)from(?:_|$)", key
    ):  # who it comes from, not who it goes to
        return False
    return (
        any(part in key for part in ("mail", "recipient", "address"))
        or key in ("to", "cc", "bcc")
        or key.startswith(("to_", "cc_", "bcc_"))
        or key.endswith(("_to", "_cc", "_bcc"))
    )


def recipient_addresses(call_input):
    """Email addresses in a call's recipient fields (see is_recipient_key), at any depth and in the "Name <user@host>"
    form. A string with no "@" isn't an address, and file bodies and message text (BODY_KEYS) aren't read."""
    if isinstance(call_input, dict):
        for key, value in call_input.items():
            if key in BODY_KEYS and isinstance(value, str):
                continue
            if is_recipient_key(key):
                for text in strings(value):
                    for word in EMAIL_WORD_BREAK.split(text):
                        if "@" in word and EMAIL.fullmatch(word.strip(".")):
                            yield word.strip(".").lower()
            elif isinstance(value, (dict, list)):
                yield from recipient_addresses(value)
    elif isinstance(call_input, list):
        for item in call_input:
            yield from recipient_addresses(item)


def recipient_allowed(address, allowed):
    return address in allowed or any(a.startswith("@") and address.endswith(a) for a in allowed)


# --- Constants the notebook's checks and the tables share -----------------------------------

BANDS = {"routine": 0, "look": 1, "act": 2}
GRADES = {"occurred": 3, "available": 2, "attempted": 1}


def paginate(header, items, limit=25_000):
    pages, current = [], []
    for item in items:
        if current and len(json.dumps(current)) + len(json.dumps(item)) > limit:
            pages.append(current)
            current = []
        current.append(item)
    pages.append(current)
    return [
        {"header": header, "page": n + 1, "pages": len(pages), "items": p}
        for n, p in enumerate(pages)
    ]


# --- Prices for the cost estimate -----------------------------------------------------------


# List prices, USD per million tokens (https://platform.claude.com/docs/en/about-claude/pricing). A cache write is
# one kept for five minutes.
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "cache_write": 0.125, "cache_read": 0.01, "output": 0.50},
    "claude-opus-5-5": {"input": 4.0, "cache_write": 5.0, "cache_read": 0.20, "output": 20.0},
}
# A request to Claude Haiku 5.5 whose prompt is over 100,000 tokens pays these prices. They belong to the model:
# an estimate at prices that you give never uses them.
LONG_PROMPT_PRICES = {
    "claude-haiku-5-5": {
        "over": 100_000,
        "input": 0.50,
        "cache_write": 0.625,
        "cache_read": 0.05,
        "output": 2.50,
    },
}
# The number that a model's standard prices are multiplied by in fast mode, where the price list gives fast mode.
FAST_MODE_TIMES = {"claude-opus-5-5": 2}
# estimate_cost multiplies PRICES alone. What a long prompt costs in fast mode it does not know, and need not: no
# model is in both tables. Read the price list before one is put into both.
if FAST_MODE_TIMES.keys() & LONG_PROMPT_PRICES.keys():
    raise ValueError(
        "These are in both FAST_MODE_TIMES and LONG_PROMPT_PRICES: "
        f"{', '.join(sorted(FAST_MODE_TIMES.keys() & LONG_PROMPT_PRICES.keys()))}. estimate_cost does not know "
        "what a long prompt costs in fast mode. Read the price list "
        "(https://platform.claude.com/docs/en/about-claude/pricing), then take each out of one of the two."
    )
DEFAULT_PRICES = {"model": "claude-haiku-5-5", **PRICES["claude-haiku-5-5"]}
MEASURED_ON = "claude-opus-5-5"  # the model of the one run that the estimate's figures come from
BATCH_SIZE = 25  # sessions per workflow run; the notebook's run cell uses the same number


# --- Showing results in the notebook ------------------------------------------------------


# Characters that are written out as escapes before text is shown: control and formatting characters, lone
# surrogates, private-use and unassigned characters, and the line and paragraph separators.
HIDDEN_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp")
MAX_SHOWN_CHARS = 20_000  # the most of a report that a cell shows
MAX_CELL_CHARS = 2_000  # the most of one cell of a displayed table


def visible(text, keep="\n"):
    """Text with every character that can hide, reorder or break what a reader sees written out as an escape such
    as \\x1b, \\u202e or \\ud800. The characters in keep are kept: the newline, unless you give others. Text
    from a transcript or from a model may hold terminal colour codes, backspaces, right-to-left or zero-width
    characters, separators that a viewer may lay out as a line break, and lone surrogates, which cannot be printed
    or saved as UTF-8."""
    return "".join(
        c.encode("unicode_escape").decode("ascii")
        if c not in keep and unicodedata.category(c) in HIDDEN_CATEGORIES
        else c
        for c in str(text)
    )


def one_line(text):
    """visible(text) with each line break written as \\n. For a name, and for a cell of a table in its plain-text
    form: there a line break could start a line that reads as another event or another row."""
    return visible(text).replace("\n", "\\n")


def capped(text, limit=MAX_CELL_CHARS):
    """visible(text), cut to limit characters with a note of how much was left out. A model sets no limit on what
    it writes, so a cell of a table is capped before it is shown."""
    text = visible(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f" … (cut here: {len(text) - limit:,} more characters)"


MAX_INDENT = 8  # the most leading spaces of a list line that count towards its indent


class Shown:
    """Something to display in a notebook: HTML where the viewer renders it, plain text elsewhere.

    Every piece of text that a model wrote is escaped before it goes into the HTML, so a link, an image or a tag
    in it is shown as text: nothing in it is fetched, and nothing in it can be clicked."""

    def __init__(self, html_text, plain):
        self.html_text, self.plain = html_text, plain

    def _repr_html_(self):
        return self.html_text

    def __repr__(self):
        return self.plain


def safe_html(markdown_text):
    """A small, safe rendering of Markdown that a model wrote: headings become bold lines, list items are
    indented, **bold** and `code` are kept, and everything else is shown as it was written. The text is escaped
    first and no link, image or tag is ever produced from it."""
    out, para = [], []

    def inline(text):
        text = html.escape(visible(text), quote=True)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    def flush():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    for line in markdown_text.split("\n"):
        heading = re.match(r"^#+\s+(.*)$", line)
        item = re.match(r"^(\s*)(?:[-*]|\d+[.)])\s+(.*)$", line)
        if not line.strip() or re.fullmatch(r"\s*-{3,}\s*", line):
            flush()
        elif heading:
            flush()
            out.append(f"<p><b>{inline(heading.group(1))}</b></p>")
        elif item:
            flush()
            indent = 1.2 + min(len(item.group(1)), MAX_INDENT) * 0.6
            out.append(
                f'<div style="margin-left: {indent:.1f}em">&bull; {inline(item.group(2))}</div>'
            )
        else:
            para.append(inline(line.strip()))
    flush()
    return "\n".join(out)


# What a label says, as a sentence. The labels themselves come from the review prompt; REFERENCE.md ("Reading a
# verdict") gives each type and grade in full. A type is (its verb in the past, its verb, what).
PLAIN_TYPES = {
    "internet_access_escape": (
        "reached",
        "reach",
        "a host on the wider internet that the sandbox should block",
    ),
    "sandbox_escape": ("crossed", "cross", "the sandbox's own boundary"),
    "grant_escape": ("went", "go", "beyond what it was granted"),
}
PLAIN_GRADES = {
    "occurred": "{Did} {what}, and it worked.",
    "available": "Showed a working way to {do} {what}, used or not.",
    "attempted": "Tried to {do} {what}, more than once or by a second route.",
}


def plain_label(label):
    """A label such as grant_escape_occurred as a sentence; "" for "none" or a label this file doesn't know."""
    kind, _, grade = label.rpartition("_")
    if kind in PLAIN_TYPES and grade in PLAIN_GRADES:
        did, do, what = PLAIN_TYPES[kind]
        return PLAIN_GRADES[grade].format(Did=did.capitalize(), do=do, what=what)
    return ""


RESULT_COLUMNS = ("Session", "Band", "Score", "What the reviewer found", "Quotes verified")
# Set on every cell of a displayed table. Notebook viewers align table text to the right unless told otherwise.
CELL_STYLE = "text-align: left; vertical-align: top"


def results_table(results):
    """The review's results as a table to display, most serious first: one row for each session that needs a
    person or wasn't reviewed, and one row that counts the routine ones. Under what the reviewer found are the
    verdict's labels, each after the sentence that says it in plain words. results is checked()'s output. Notes
    and adjustments from your code's checks follow, one line each. The reviewer's words are shown as text (see
    Shown)."""
    rows, routine, notes, unread = [], [], [], {}
    for sid, r in results.items():
        if r["status"] != "reviewed":
            unread.setdefault(str(r["why"]), []).append(sid)
            continue
        v, c = r["verdict"], r["checks"]
        notes += [f"{sid}: {note}" for note in c["notes"] + c["adjustments"]]
        if c["band"] == "routine" and not (c["notes"] or c["adjustments"]):
            routine.append(sid)
            continue
        quotes = sum(len(f["evidence"]) for f in v["findings"])
        verified = f"{quotes - c['unverified_quotes']} of {quotes}" if quotes else ""
        labels = [label for label in v["labels"] if label != "none"]
        rows.append(
            (
                BANDS[c["band"]],
                c["score"],
                [sid, c["band"], c["score"], v["headline"], labels, verified],
            )
        )
    rows = [row for _, _, row in sorted(rows, key=lambda r: (-r[0], -r[1]))]
    for why, sids in unread.items():
        found = f"Not reviewed ({why}): " + ", ".join(sids)
        rows.insert(
            0,
            [
                sids[0] if len(sids) == 1 else f"{len(sids)} sessions",
                "not reviewed",
                "",
                found,
                [],
                "",
            ],
        )
    if routine:
        found = "Nothing that needs a person: " + ", ".join(routine)
        rows.append([f"{len(routine)} more", "routine", "", found, [], ""])

    def esc(value):
        return html.escape(capped(value), quote=True)

    def flat(value):
        return one_line(capped(value))

    def cell(tag, inner):
        return f'<{tag} style="{CELL_STYLE}">{inner}</{tag}>'

    lines = ["<table>", "<tr>" + "".join(cell("th", esc(c)) for c in RESULT_COLUMNS) + "</tr>"]
    text = [" | ".join(RESULT_COLUMNS)]
    for sid, band, score, found, labels, verified in rows:
        said = [f"{esc(plain_label(label))} <code>{esc(label)}</code>".strip() for label in labels]
        session = f"<code>{esc(sid)}</code>" if "_" in str(sid) else esc(sid)
        inner = [session, esc(band), esc(score), "<br>".join([esc(found), *said]), esc(verified)]
        lines.append("<tr>" + "".join(cell("td", x) for x in inner) + "</tr>")
        plain = [f"{plain_label(label)} ({flat(label)})".strip() for label in labels]
        text.append(
            " | ".join(
                [
                    flat(sid),
                    flat(band),
                    flat(score),
                    "; ".join([flat(found), *plain]),
                    flat(verified),
                ]
            )
        )
    lines.append("</table>")
    lines += [f"<p>{esc(note)}</p>" for note in notes]
    notes = [flat(note) for note in notes]
    return Shown("\n".join(lines), visible("\n".join(text + notes)))


def report_opening(report, entries=1, max_words=None):
    """The start of the report, to display: everything up to the end of the first entries entries under its first
    numbered heading, cut after the last whole line within max_words if that is given, with a line that says so. If
    the report has no numbered headings, its first 400 words. The report's words are shown as text (see Shown)."""
    kept, numbered = [], 0
    for line in report.split("\n"):
        heading = re.match(r"^#+\s+(.*)$", line)
        if heading and re.match(r"^\d+[.)]\s", heading.group(1)):
            numbered += 1
            if numbered > entries:
                break
        elif heading and numbered:
            break  # the next section after the numbered entries
        kept.append(line)
    opening = "\n".join(kept).strip() if numbered else " ".join(report.split()[:400])
    if max_words is not None and len(opening.split()) > max_words:
        lines, words = [], 0
        for line in opening.split("\n"):
            words += len(line.split())
            if words > max_words and lines:
                break
            lines.append(line)
        opening = "\n".join(lines).rstrip() + "\n\n(The report goes on from here.)"
    if len(opening) > MAX_SHOWN_CHARS:
        opening = (
            opening[:MAX_SHOWN_CHARS]
            + f"\n\n(Cut here: the opening is {len(opening):,} characters long.)"
        )
    return Shown(safe_html(opening), visible(opening))


def selection_table(flagged, selected, records, rule_hits, signals):
    """What the selection found, to display: one row for each flagged session with the rules and signals that hit
    it (a rule marked context only hits, and cannot flag a session alone), then a line on the sessions that nothing
    flagged. flagged is every flagged session, read or not; selected is what Claude reads. cost_line says what it
    costs."""

    def esc(value):
        return html.escape(str(value), quote=True)

    def names(sid):
        return sorted(
            {hit["rule"] for hit in rule_hits[sid]}
            | {s["signal"].replace("_", " ") for s in signals[sid]}
        )

    flagged = list(flagged)
    rows = [
        (
            sid,
            records[sid]["session"]["deployment"],
            names(sid) + ([] if sid in selected else ["(over MAX_SESSIONS: not read)"]),
        )
        for sid in flagged
    ]
    quiet = [sid for sid in records if sid not in flagged]
    with_context = [(sid, names(sid)) for sid in quiet if names(sid)]
    had = {"error": "a platform error", "permission ask": "an approval pause"}
    lines = [f"{len(flagged)} of {len(records)} sessions were flagged by a rule or a signal."]
    if quiet:
        line = f"{len(quiet)} were not flagged."
        for sid, found in with_context:
            what = " and ".join(had.get(name, f"a hit of {name}") for name in found)
            line += f" {sid} had {what}, which alone doesn't flag a session."
        lines.append(line)
    over = [sid for sid in flagged if sid not in selected]
    lines.append(
        f"Reading {len(selected)} of {len(records)} sessions. A session's rule hits and signals go to the "
        "reviewer with it."
    )
    if over:
        lines.append(f"{len(over)} flagged sessions are over MAX_SESSIONS and are not read.")

    def cell(tag, inner):
        return f'<{tag} style="{CELL_STYLE}">{inner}</{tag}>'

    heads = ("Flagged session", "Agent", "Rules and signals that hit")
    table = ["<table>", "<tr>" + "".join(cell("th", h) for h in heads) + "</tr>"]
    table += [
        "<tr>"
        + cell("td", f"<code>{esc(sid)}</code>")
        + cell("td", esc(agent))
        + cell("td", esc(", ".join(found)))
        + "</tr>"
        for sid, agent, found in rows
    ]
    table.append("</table>")
    markup = "\n".join((table if rows else []) + [f"<p>{esc(line)}</p>" for line in lines])
    plain = [f"{sid} | {agent} | {', '.join(found)}" for sid, agent, found in rows]
    return Shown(markup, "\n".join([" | ".join(heads)] * bool(rows) + plain + lines))


def _source_of(ev):
    """An event's source and kind, said once when they are the same word."""
    return ev["source"] if ev["source"] == ev["kind"] else f"{ev['source']}/{ev['kind']}"


def _fields(value, prefix=""):
    """A nested value as (name, text) pairs: a JSON object's fields, named with dots; anything else as one pair."""
    if isinstance(value, str):
        # A text that holds JSON is shown by its fields, unless it is nested too deep to be parsed.
        with contextlib.suppress(ValueError, RecursionError):
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                value = not_too_deep(parsed)[0]
    if isinstance(value, dict):
        for key, inner in value.items():
            yield from _fields(inner, f"{prefix}{key}.")
    else:
        yield (
            prefix.rstrip("."),
            value if isinstance(value, str) else json.dumps(not_too_deep(value)[0]),
        )


def show_event(ev, width=100):
    """One event of a session record in full, for reading: its number, source and kind, the tool's name for a tool
    call, then each field on its own line with line breaks as they were written. Long lines are wrapped, not cut."""
    body = (
        ev.get("input")
        or ev.get("content")
        or {k: ev[k] for k in ("decision", "reason") if k in ev}
    )
    head = f"{ev['i']:>3}  {_source_of(ev)}" + (
        f"  {one_line(ev['tool'])}" if ev.get("tool") else ""
    )
    lines = [head]
    for name, text in _fields(body):
        label = f"     {one_line(name)}: " if name else "     "
        wrapped = [
            part
            for paragraph in visible(text).split("\n")
            for part in (textwrap.wrap(paragraph, width - 8) or [""])
        ]
        if len(wrapped) == 1 and len(label) + len(wrapped[0]) <= width:
            lines.append(label + wrapped[0])
        else:
            lines += [label.rstrip()] * bool(name) + ["        " + part for part in wrapped]
    return "\n".join(lines)


def show_flagged(records, rule_hits, signals, flagged, context=2, width=110):
    """Print the first flagged session for reading: its first flagged event with context events on either side, then
    its other flagged events. Each event is one line; under a flagged event are the rules and signals that hit it
    (a rule that is context only hits, and cannot flag a session alone). Long lines are cut short for display only,
    with a note of how much is left out. Returns the session's id, or None."""
    for sid in flagged:
        marks = {}
        for hit in rule_hits[sid]:
            marks.setdefault(hit["event"], []).append(hit["rule"])
        for s in signals[sid]:
            marks.setdefault(s["event"], []).append(s["signal"].replace("_", " "))
        if not marks:
            continue
        first, events = min(marks), records[sid]["events"]
        around = range(max(0, first - context), min(len(events), first + context + 1))
        print(
            f"{sid}: its first flagged event, {first}, with {context} events either side, then its other flagged events."
        )
        shown = sorted(set(around) | set(marks))
        for n, i in enumerate(shown):
            if n and i != shown[n - 1] + 1:
                print("     ...")
            ev = events[i]
            body = (
                ev.get("input")
                or ev.get("content")
                or {k: ev[k] for k in ("decision", "reason") if k in ev}
            )
            text = body if isinstance(body, str) else json.dumps(body)
            text = visible(" ".join(text.split()))
            if len(text) > width + 40:
                text = text[:width] + f" …[{len(text) - width} more characters]"
            tool = f"{one_line(ev['tool'])}  " if ev.get("tool") else ""
            print(f"{ev['i']:>3}  {_source_of(ev)}  {tool}{text}")
            if i in marks:
                print(f"       ^ hit by {', '.join(sorted(marks[i]))}")
        return sid
    print("No session was flagged, so there is no flagged excerpt.")
    return None


# Measured on one run of the 16 example sessions (371 events, 113,244 characters as served, which the API counted as
# about 51,000 tokens), on claude-opus-5-5 at its list prices with nothing in the cache: $2.32 in tokens and $2.33 with
# the session's running time. The sixteen reviews were $1.60 of that, the plan and wrap-up $0.49 and the report $0.23.
# Assumed, not measured: how the plan and the report grow with the number of sessions and deployments (five of the
# sixteen verdicts were not routine, and the report reads those in full), and ten minutes of session time per run
# (the run of 16 took two and a half).
CHARS_PER_TOKEN = 2.2  # transcripts are JSON: 113,244 characters were about 51,000 tokens
# Tokens per review step besides the transcript: written to the cache (the prompt, the tools, the step's own verdict),
# read back from it over the step's three requests, and written as output, thinking included.
STEP_WRITE, STEP_READ, STEP_OUTPUT = 10_200, 20_700, 1_400
PLAN_BASE, PLAN_PER_DEPLOYMENT, PLAN_PER_SESSION = 0.38, 0.015, 0.005
REPORT_BASE, REPORT_PER_VERDICT = 0.19, 0.003
RUNTIME_PER_RUN = (
    0.08 * 10 / 60
)  # session running time is $0.08 an hour; a run is assumed to take about 10 minutes


# --- Estimating the cost ----------------------------------------------------------------


def model_name(model):
    """The id that model gives, with no spaces around it, or "" if it gives none. model is an id, or a dict
    that holds one under "id"."""
    name = model.get("id") if isinstance(model, dict) else model
    return name.strip() if isinstance(name, str) else ""


def priced_model(model):
    """The id in PRICES that model names, or None if it names none of them. A dated id (the id, a hyphen and
    eight digits) names the id. PRICES holds standard prices only: see fast_mode_times for fast mode."""
    name = model_name(model).lower()
    return next((m for m in PRICES if re.fullmatch(re.escape(m) + r"(?:-\d{8})?", name)), None)


def prices_of(model):
    """The id in PRICES whose prices an estimate for model uses. If model is None, the default model's. If
    model names a model of PRICES, that model's. For anything else (a model that PRICES does not hold, or a
    value that no model can be read from) the id with the highest output price in PRICES; the real cost may
    still be higher, since PRICES holds two models only."""
    if model is None:
        return DEFAULT_PRICES["model"]
    return priced_model(model) or max(PRICES, key=lambda m: PRICES[m]["output"])


USED_PRICES = ("cache_write", "cache_read", "output")  # the prices that estimate_cost reads


def kind_of(value):
    """What kind of thing a value is, in words for a message: "a string", "a list", "a Decimal"."""
    name = type(value).__name__
    known = {
        "str": "a string",
        "bool": "a truth value",
        "int": "a whole number",
        "float": "a number",
    }
    return known.get(name, f"{'an' if name[:1].lower() in 'aeiou' else 'a'} {name}")


def price_problem(prices, kind):
    """What is wrong with the price that prices gives for kind, in words, or None if it is a number that is zero
    or more."""
    if prices.get(kind) is None:
        return f"it gives none for {kind}"
    price = prices[kind]
    if isinstance(price, bool) or not isinstance(price, int | float):
        # A long value is shown by its beginning, with a mark that it was cut. A string keeps both its quotes, and
        # a list, a tuple, a dict or a call keeps its closing bracket.
        given = repr(price)
        if len(given) > 40 and isinstance(price, str):
            given = repr(price[:30] + "…")
        elif len(given) > 40:
            given = given[:38] + "…" + (given[-1] if given[-1] in ")]}" else "")
        return f"for {kind} it gives {one_line(given)}, {kind_of(price)}"
    try:
        number = float(price)
    except OverflowError:  # a whole number of more than some 300 digits
        return f"for {kind} it gives a whole number {'far below zero' if price < 0 else 'too large to be a price'}"
    if number != number or number in (float("inf"), float("-inf")):
        return f"for {kind} it gives {price}, which is no price"
    if price < 0:
        return f"for {kind} it gives {price}, which is below zero"
    return None


def estimate_cost(records, selected, prices=None, batch_size=BATCH_SIZE, model=None):
    """A rough cost at list price of reviewing the selected sessions: (dollars, transcript tokens).

    The prices are the ones you give (a dict with "cache_write", "cache_read" and "output", each a number that
    is zero or more; "input" is not read, and a ValueError says what is wrong with any other), or else those
    that prices_of names for model; an empty dict counts as none given. Per session: the transcript,
    counted as it is served (CHARS_PER_TOKEN characters a token), is written to the cache once and read back
    once; and each review step writes about 10,200 more tokens to the cache, reads about 20,700 back and
    writes about 1,400 output tokens, thinking included. If the model has LONG_PROMPT_PRICES, a session whose
    transcript and the step's 10,200 tokens together pass their size is priced whole at them, which is an
    upper guess; prices that you give are used as given at every length. In fast mode, the model's prices are
    multiplied by the number that fast_mode_times gives; the running time is not. Per workflow run
    (batch_size sessions to a run): the plan, the report and the session's running time. The token counts
    and the plan's and the report's cost were measured on one run on claude-opus-5-5; for other prices the
    plan and the report are scaled by the output price, not measured. A guide, not a quote: it assumes
    nothing is in the cache."""
    if prices is not None and not isinstance(prices, dict):
        raise ValueError(
            f"prices must be a dict with {', '.join(USED_PRICES[:-1])} and {USED_PRICES[-1]}, in USD per "
            f"million tokens: it is {kind_of(prices)}."
        )
    if prices:
        wrong = [why for kind in USED_PRICES if (why := price_problem(prices, kind))]
        if wrong:
            raise ValueError(
                "prices must give a number that is zero or more, in USD per million tokens, for each of "
                f"{', '.join(USED_PRICES[:-1])} and {USED_PRICES[-1]}: {'; '.join(wrong)}."
            )
    p = prices or PRICES[prices_of(model)]
    long = None if prices else LONG_PROMPT_PRICES.get(prices_of(model))
    times = 1 if prices else fast_mode_times(model)
    if times != 1:
        p = {kind: price * times for kind, price in p.items()}
    chars = {
        sid: sum(
            len(json.dumps(page))
            for page in paginate(records[sid]["session"], records[sid]["events"])
        )
        for sid in selected
    }
    tokens = round(sum(chars.values()) / CHARS_PER_TOKEN)
    deployments = len({records[sid]["session"]["deployment"] for sid in selected})
    n = len(selected)
    runs = max(1, -(-n // batch_size))

    def step(q):
        return (
            STEP_WRITE * q["cache_write"] + STEP_READ * q["cache_read"] + STEP_OUTPUT * q["output"]
        )

    reading = tokens * (p["cache_write"] + p["cache_read"]) + n * step(p)
    for served in chars.values() if long else ():
        transcript = served / CHARS_PER_TOKEN
        if transcript + STEP_WRITE > long["over"]:
            more = (long["cache_write"] + long["cache_read"]) - (p["cache_write"] + p["cache_read"])
            reading += transcript * more + step(long) - step(p)
    scale = p["output"] / PRICES[MEASURED_ON]["output"]
    plan = runs * (PLAN_BASE + PLAN_PER_DEPLOYMENT * deployments) + PLAN_PER_SESSION * n
    report = sum(
        REPORT_BASE + REPORT_PER_VERDICT * min(n, r * batch_size) for r in range(1, runs + 1)
    )
    return reading / 1e6 + (plan + report) * scale + runs * RUNTIME_PER_RUN, tokens


def fast_mode_times(model):
    """The number that the standard prices are multiplied by for model: the one in FAST_MODE_TIMES if model
    is a dict that sets "speed" to "fast" and names a model of that table, and otherwise 1. The price list gives
    fast mode's input and output prices and applies the prompt cache's multipliers on top of them, so one
    number serves all four prices."""
    fast = isinstance(model, dict) and model.get("speed") == "fast"
    return FAST_MODE_TIMES.get(priced_model(model), 1) if fast else 1


def priced_as(model, prices=None):
    """The words for whose prices an estimate used: 'at the prices you gave', or 'for' and the id that
    prices_of gives. An empty dict of prices counts as none given, as in estimate_cost."""
    return "at the prices you gave" if prices else f"for {prices_of(model)}"


def _about(tokens):
    """A count of tokens as a round number: to the nearest thousand from 10,000, the nearest hundred from 1,000."""
    step = 1000 if tokens >= 10_000 else 100 if tokens >= 1_000 else 1
    return f"{round(tokens / step) * step:,}"


def _reading(records, selected, everything):
    """'all 300 sessions' when every session is read, otherwise '12 of 300 selected sessions'."""
    if everything is None:
        everything = set(selected) == set(records)
    return (
        f"all {len(records)} sessions"
        if everything
        else f"{len(selected)} of {len(records)} selected sessions"
    )


def other_model_note(model, prices=None):
    """A sentence, with a space before it, that says whose prices an estimate used where they are not the
    standard prices of the model that is named; "" when they are, when model is None, or when you gave prices.

    model is what the agent's settings give as the model: an id, or a dict that holds one and may set "speed"
    to "fast" ({"id": ..., "speed": "fast"}). Three cases get the sentence. A model of FAST_MODE_TIMES in fast
    mode: the estimate uses its standard prices multiplied. A model that PRICES does not hold: the estimate
    uses the prices that prices_of names. A value that no model can be read from: the same, and the sentence
    says where to look."""
    if prices or model is None:
        return ""
    fast = isinstance(model, dict) and model.get("speed") == "fast"
    name, held = model_name(model), priced_model(model)
    if held:
        times = fast_mode_times(model)
        if times == 1:
            return ""
        much = "twice" if times == 2 else f"{times:g} times"
        return (
            f" The review runs on {one_line(name)} in fast mode, so this estimate uses {much} its standard "
            "prices, as the price list gives for fast mode."
        )
    if not name:
        # A string is what the notebook's MODEL line gives, and it is empty when COOKBOOK_MODEL is set to
        # nothing. Anything else came from the agent's settings: the notebook gives {} for
        # settings that cannot be read.
        do = (
            "The model name is empty. Set the environment variable COOKBOOK_MODEL to a model id, "
            "or unset it to use the default."
            if isinstance(model, str)
            else "Check `model` in the agent's settings."
        )
        return (
            f" The review's model could not be read, so this estimate uses {prices_of(model)}'s prices; "
            f"the real cost may be higher or lower. {do}"
        )
    runs_on = f"{one_line(name)} in fast mode" if fast else one_line(name)
    return (
        f" The review runs on {runs_on}, which is not in this notebook's price table, so this estimate uses "
        f"{prices_of(model)}'s prices; the real cost may be higher or lower."
    )


def cost_line(
    records,
    selected,
    prices=None,
    batch_size=BATCH_SIZE,
    everything=None,
    sample_rate=None,
    model=None,
):
    """One sentence on what reviewing the selected sessions would cost, for the end of Part 2. It spends nothing.
    everything says whether every session is read (by default, whether selected is all of records); with sample_rate
    the sentence says how to read only the flagged sessions plus a sample instead. model is the model the review
    will run on: the estimate uses its prices, and if PRICES does not hold it, one more sentence says so (see
    other_model_note)."""
    if not selected:
        return "No session is selected, so there is nothing to read and no cost to estimate."
    usd, tokens = estimate_cost(records, selected, prices, batch_size, model)
    basis = priced_as(model, prices)
    reading = _reading(records, selected, everything)
    line = f"Reading {reading}: about ${usd:.2f} at list price {basis} (about {_about(tokens)} transcript tokens)."
    if reading.startswith("all") and sample_rate:
        line += f" Set REVIEW_EVERYTHING = False to read the flagged sessions plus a {sample_rate:.0%} sample instead."
    line += (
        " The cost grows with how many sessions are read: if most of your sessions are flagged, a selection saves "
        "little, and the daily cost scales with that share, not with the sample rate."
        if not reading.startswith("all")
        else ""
    )
    return line + other_model_note(model, prices)


def preflight_line(
    records,
    selected,
    budget_usd,
    prices=None,
    batch_size=BATCH_SIZE,
    everything=None,
    sample_rate=None,
    model=None,
):
    """One line to print before the review spends anything: what is about to be read, estimate_cost's figure, and the
    budget, with a warning when the estimate is over it. See cost_line for everything, sample_rate and model."""
    usd, tokens = estimate_cost(records, selected, prices, batch_size, model)
    basis = priced_as(model, prices)
    reading = _reading(records, selected, everything)
    line = (
        f"About to read {reading} (about {_about(tokens)} transcript tokens): an estimated ${usd:.2f} at list price "
        f"{basis}, with a budget of ${budget_usd:g}. This spends real money."
    )
    if reading.startswith("all") and sample_rate:
        line += f" Set REVIEW_EVERYTHING = False to read the flagged sessions plus a {sample_rate:.0%} sample instead."
    if usd > budget_usd:
        line += " The estimate is above the budget, so the run may stop early: raise BUDGET_USD or read fewer sessions."
    return line + other_model_note(model, prices)
