import json
import boto3
import uuid
import base64
import logging
import os
from botocore.exceptions import ClientError
import base64
from requests_toolbelt.multipart import decoder
from jsonschema import validate, ValidationError, SchemaError

metadata_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "customer_id": {
            "type": "string",
            "pattern": "^C[0-9]+$"
        },
        "agent_id": {
            "type": "string",
            "pattern": "^A[0-9]+$"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "call_duration": {
            "type": "integer",
            "minimum": 1
        },
        "audio_format": {
            "type": "string",
            "enum": ["wav", "mp3", "flac"]
        }
    },
    "required": ["customer_id", "agent_id", "timestamp", "call_duration", "audio_format"],
    "additionalProperties": False
}

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create clients for AWS services
s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')
sqs = boto3.client('sqs')

# Get environment variables
bucket_name = os.environ['BUCKET_NAME']
table_name = os.environ['TABLE_NAME']
queue_url = os.environ['QUEUE_URL']

# extract and validate metadata
def extract_and_validate_metadata(part):
    try:
        metadata = json.loads(part.content.decode('utf-8'))
        validate(instance=metadata, schema=metadata_schema)
        return metadata
    except (json.JSONDecodeError, ValidationError, SchemaError) as e:
        logger.info(f"Invalid metadata: {str(e)}")
        return {
            'statusCode': 400,
            'body': f"Invalid metadata: {str(e)}"
        }

def lambda_handler(event, context):
    try:
        if event['isBase64Encoded']:
            body = base64.b64decode(event['body'])
        else:
            body = event['body']
        content_type = event['headers']['content-type']
        multipart_data = decoder.MultipartDecoder(body, content_type)

        audio_file = None
        metadata = None

        for part in multipart_data.parts:
            if part.headers[b"Content-Disposition"].decode().find('name="audio"') != -1:
                audio_file = part.content
            elif part.headers[b"Content-Disposition"].decode().find('name="metadata"') != -1:
                metadata = extract_and_validate_metadata(part)
        
        if not audio_file or not metadata:
            logger.info("Missing audio file or metadata")
            return {
                'statusCode': 400,
                'body': "Missing audio file or metadata"
            }
    
        interaction_id = str(uuid.uuid4())
        audio_format = metadata['audio_format']
        audio_file_key = f'audio/{interaction_id}.{audio_format}'

        # Upload the audio file to the S3 bucket
        try:
            s3.put_object(Bucket=bucket_name, Key=audio_file_key, Body=audio_file)
            logger.info(f"Uploaded audio file to s3://{bucket_name}/{audio_file_key}")
        except ClientError as e:
            logger.error(f"Error uploading audio file: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps(str(e))
            }
        
        # create the data that will be stored in the dynamodb table
        item = {
            'interaction_id': {'S': interaction_id},
            'customer_id': {'S': metadata['customer_id']},
            'agent_id': {'S': metadata['agent_id']},
            'timestamp': {'S': metadata['timestamp']},
            'call_duration': {'N': str(metadata['call_duration'])},
            'audio_format': {'S': metadata['audio_format']},
            'audio_file_key': {'S': audio_file_key},
            'status': {'S': 'Uploaded'}
        }
        # put the item into the dynamodb table
        try:
            dynamodb.put_item(TableName=table_name, Item=item)
            logger.info(f"Inserted item into DynamoDB table {table_name}")
        except ClientError as e:
            logger.error(f"Error inserting item into DynamoDB table: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps(str(e))
            }
        
        try:
            # Send message to SQS queue the interaction_id and audio_file_key and the audio format to the SQS queue
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    'interaction_id': interaction_id,
                    'audio_file_key': audio_file_key,
                    'audio_format': audio_format
                })
            )
            logger.info(f"Sent message to SQS queue {queue_url}")
        except ClientError as e:
            logger.error(f"Error sending message to SQS queue: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps(str(e))
            }
        # If Aal Izz Well, return 200
        logger.info('Request processed successfully.')
        return {
            'statusCode': 200,
            'body': json.dumps('Request processed successfully.')
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }