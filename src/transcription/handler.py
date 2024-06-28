import os
import json
import boto3
import base64
import logging
import uuid

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# create clients for AWS services
s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
dynamodb = boto3.client('dynamodb')

# get environment variables
input_bucket_name = os.environ['AUDIO_BUCKET']
output_bucket_name = os.environ['TRANSCRIPTION_BUCKET']
table_name = os.environ['TABLE_NAME']

# lambda handler function
def lambda_handler(event, context):
    try:
        # get the interaction id, audio file key and the audio format from the event
        interaction_id = event['interaction_id']
        audio_file_key = event['audio_file_key']
        audio_format = event['audio_format']

        try:
            transcribe.start_transcription_job(
                TranscriptionJobName=interaction_id,
                LanguageCode='en-US',
                MediaFormat=audio_format,
                Media={
                    'MediaFileUri': f's3://{input_bucket_name}/{audio_file_key}'
                },
                OutputBucketName=output_bucket_name,
                OutputKey=f'transcription/{interaction_id}.json',
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 2
                }
            )
            logger.info(f"Transcription job started for interaction {interaction_id}")
            update_interaction_status(interaction_id, 'transcribing')
        except Exception as e:
            logger.error(f"Error starting transcription job: {str(e)}")
            update_interaction_status(interaction_id, 'error starting transcription job')
    except Exception as e:
        logger.error(f"Error handling transcription: {str(e)}")


def update_interaction_status(interaction_id, status):
    try:
        dynamodb.update_item(
            TableName=table_name,
            Key={'interaction_id': {'S': interaction_id}},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': {'S': status}}
        )
        logger.info(f"Updated status for interaction {interaction_id} to '{status}'")
    except Exception as e:
        logger.error(f"Error updating status for interaction {interaction_id}: {str(e)}")
        raise e 