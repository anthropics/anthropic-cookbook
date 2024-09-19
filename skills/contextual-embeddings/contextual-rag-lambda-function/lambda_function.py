import json
import os
import logging
import traceback
from inference_adapter import InferenceAdapter
from s3_adapter import S3Adapter

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

contextual_retrieval_prompt = """
    <document>
    {doc_content}
    </document>


    Here is the chunk we want to situate within the whole document
    <chunk>
    {chunk_content}
    </chunk>


    Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk.
    Answer only with the succinct context and nothing else.
    """

def lambda_handler(event, context):
    logger.debug('input={}'.format(json.dumps(event)))

    s3_adapter = S3Adapter()
    inference_adapter = InferenceAdapter()

    # Extract relevant information from the input event
    input_files = event.get('inputFiles')
    input_bucket = event.get('bucketName')

    if not all([input_files, input_bucket]):
        raise ValueError("Missing required input parameters")

    output_files = []
    for input_file in input_files:

        processed_batches = []
        for batch in input_file.get('contentBatches'):

            # Get chunks from S3
            input_key = batch.get('key')

            if not input_key:
                raise ValueError("Missing uri in content batch")

            # Read file from S3
            file_content = s3_adapter.read_from_s3(bucket_name=input_bucket, file_name=input_key)
            print(file_content.get('fileContents'))

            # Combine all chunks together to build content of original file
            # Alternatively we can also read original file and extract text from it
            original_document_content = ''.join(content.get('contentBody') for content in file_content.get('fileContents') if content)

            # Process one chunk at a time
            chunked_content = {
                'fileContents': []
            }
            for content in file_content.get('fileContents'):
                content_body = content.get('contentBody', '')
                content_type = content.get('contentType', '')
                content_metadata = content.get('contentMetadata', {})

                # Update chunk with additional context
                prompt = contextual_retrieval_prompt.format(doc_content=original_document_content, chunk_content=content_body)
                response_stream = inference_adapter.invoke_model_with_response_stream(prompt)
                chunk_context = ''.join(chunk for chunk in response_stream if chunk)

                # append chunk to output file content
                chunked_content['fileContents'].append({
                    "contentBody": chunk_context + "\n\n" + content_body,
                    "contentType": content_type,
                    "contentMetadata": content_metadata,
                })

            output_key = f"Output/{input_key}"

            # write updated chunk to output S3
            s3_adapter.write_output_to_s3(input_bucket, output_key, chunked_content)

            # Append the processed chunks file to list of files
            processed_batches.append({ "key": output_key })
        output_files.append({
            "originalFileLocation": input_file.get('originalFileLocation'),
            "fileMetadata": {},
            "contentBatches": processed_batches
        })

    return {
        "outputFiles": output_files
    }