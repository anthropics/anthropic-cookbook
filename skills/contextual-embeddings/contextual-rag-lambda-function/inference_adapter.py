import json
import boto3
import os
from botocore.exceptions import ClientError

class InferenceAdapter:

    def __init__(self):
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name='us-east-1' #change region as needed
        )
        self.model_id = 'anthropic.claude-3-haiku-20240307-v1:0'

    def invoke_model_with_response_stream(self, prompt, max_tokens=1000):

        request_body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.0,
            })

        # Invoke the model
        try:
            response = self.bedrock_runtime.invoke_model_with_response_stream(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=request_body
            )

            for event in response.get('body'):
                chunk = json.loads(event['chunk']['bytes'].decode())
                if chunk['type'] == 'content_block_delta':
                    yield chunk['delta']['text']
                elif chunk['type'] == 'message_delta':
                    if 'stop_reason' in chunk['delta']:
                        break

        except ClientError as e:
            print(f"An error occurred: {e}")
            yield None