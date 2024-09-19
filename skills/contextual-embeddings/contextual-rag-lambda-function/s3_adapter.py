import json
import boto3
import os
from botocore.exceptions import ClientError

class S3Adapter:
    def __init__(self):
        # Create an S3 client
        self.s3_client = boto3.client('s3')

    def write_output_to_s3(self, bucket_name, file_name, json_data):
        """
        Write a JSON object to an S3 bucket

        :param bucket_name: Name of the S3 bucket
        :param file_name: Name of the file to be created in the bucket
        :param json_data: JSON object to be written
        :return: True if file was uploaded, else False
        """

        try:
            # Convert JSON object to string
            json_string = json.dumps(json_data)

            # Upload the file
            response = self.s3_client.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=json_string,
                ContentType='application/json'
            )

            # Check if the upload was successful
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                print(f"Successfully uploaded {file_name} to {bucket_name}")
                return True
            else:
                print(f"Failed to upload {file_name} to {bucket_name}")
                return False

        except ClientError as e:
            print(f"Error occurred: {e}")
            return False

    def read_from_s3(self, bucket_name, file_name):
        """
        Write a JSON object to an S3 bucket

        :param bucket_name: Name of the S3 bucket
        :param file_name: Name of the file to be created in the bucket
        :return: True if file was uploaded, else False
        """
        try:
            # Get the object from S3
            response = self.s3_client.get_object(Bucket=bucket_name, Key=file_name)

            # Read the content of the file
            return json.loads(response['Body'].read().decode('utf-8'))

        except ClientError as e:
            print(f"Error reading file from S3: {str(e)}")

    def parse_s3_path(self, s3_path):
        # Remove 's3://' prefix if present
        s3_path = s3_path.replace('s3://', '')

        # Split the path into bucket and key
        parts = s3_path.split('/', 1)

        if len(parts) != 2:
            raise ValueError("Invalid S3 path format")

        bucket_name = parts[0]
        file_key = parts[1]

        return bucket_name, file_key