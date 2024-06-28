# import libraries
import os
import json
import boto3

import logging
from jinja2 import Template

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# create clients for AWS services
s3 = boto3.client('s3') 
bedrock_runtime = boto3.client('bedrock-runtime', 'us-west-2') 
sqs = boto3.client('sqs')

# get environment variables
bucket_name = os.environ['BUCKET_NAME']
queue_url = os.environ['QUEUE_URL'] 

# lambda handler function
def lambda_handler(event, context):
    try:
        # get the transcription job name and the transcript URI from the event
        detail = event['detail']
        transcription_job_name = detail['TranscriptionJobName']
        transcript_uri = detail['Transcript'].get('TranscriptFileUri')
        
        if not transcript_uri:
            raise ValueError("Invalid event structure: 'TranscriptFileUri' is missing")
        # extract the key from the URI
        key = '/'.join(transcript_uri.split('/')[3:])
        # get the transcription from the s3 bucket
        file_content = s3.get_object(Bucket=bucket_name, Key=key)['Body'].read().decode('utf-8')
        transcript= extract_transcript_from_textract(file_content)
        logger.info(f"Successfully read file {key} from bucket {bucket_name}.")
        summary= bedrock_summarisation(transcript)
        logger.info(f"Successfully summarised the transcript.")
        # send the summary over the sqs queue
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({
                'interaction_id': transcription_job_name,
                'summary': summary
            })
        )

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return {
            'statusCode': 500,
            'body': f"An error occurred: {e}"
        }
    
    return {
        'statusCode': 200,
        'body': "Success"
    }


def extract_transcript_from_textract(file_content):

    transcript_json = json.loads(file_content)

    output_text = ""
    current_speaker = None

    items = transcript_json['results']['items']

    # Iterate through the content word by word:
    for item in items:
        speaker_label = item.get('speaker_label', None)
        content = item['alternatives'][0]['content']
        
        # Start the line with the speaker label:
        if speaker_label is not None and speaker_label != current_speaker:
            current_speaker = speaker_label
            output_text += f"\n{current_speaker}: "
        
        # Add the speech content:
        if item['type'] == 'punctuation':
            output_text = output_text.rstrip() 
        
        output_text += f"{content} "
        
    return output_text


def bedrock_summarisation(transcript):

    template_string=s3.get_object(Bucket=bucket_name, Key='template.txt')['Body'].read().decode('utf-8')
    
    data = {
        'transcript': transcript
    }
    
    template = Template(template_string)
    prompt = template.render(data)
    
    kwargs = {
        "modelId": "amazon.titan-text-express-v1",
        "contentType": "application/json",
        "accept": "*/*",
        "body": json.dumps(
            {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 2048,
                    "stopSequences": [],
                    "temperature": 0,
                    "topP": 0.9
                }
            }
        )
    }
        
    response = bedrock_runtime.invoke_model(**kwargs)

    summary = json.loads(response.get('body').read()).get('results')[0].get('outputText')    
    return summary