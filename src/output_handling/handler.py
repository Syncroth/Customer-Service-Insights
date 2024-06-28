# import packages
import os
import json
import jsonschema
import jsonschema.exceptions
import boto3
import logging

# data validation schema
schema = {
    "type": "object",
    "properties": {
        "assigned_to": {"type": "string"},
        "due_date": {"type": ["string", "null"]},
        "topic": {"type": "string"},
        "satisfaction_score": {"type": "number"},
        "sentiment_analysis": {"type": "string"},
        "feedback_comments": {"type": "string"},
        "compliance_status": {"type": "string"},
        "escalation_flag": {"type": "boolean"},
        "escalation_reason": {"type": "string"},
        "agent_efficiency_score": {"type": "number"},
        "follow_up_flag": {"type": "boolean"},
        "follow_up_notes": {"type": "string"},
    },
    "required": ["assigned_to", "topic", "satisfaction_score", "sentiment_analysis", "feedback_comments", "compliance_status", "escalation_flag", "agent_efficiency_score", "follow_up_flag"],
}

# set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# create clients for AWS services
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
dynamodb = boto3.client('dynamodb') 
# get environment variables

metadata_table_name = os.environ['METADATA_TABLE']
interaction_table_name = os.environ['INTERACTION_TABLE']
queue_url = os.environ['QUEUE_URL']


def lambda_handler(event, context):
    try:
        # get the message from the SQS queue
        message = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1
        )
        message_body = json.loads(message['Messages'][0]['Body'])

        # validate the message body
        try:
            jsonschema.validate(message_body, schema)
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Invalid message body: {e}")
            return {
                'statusCode': 400,
                'body': f"Invalid message body: {e}"
            }
        interaction_id = message_body['interaction_id']
        # get agent_id, customer_id and call duration from the metadata table
        response = dynamodb.get_item(
            TableName=metadata_table_name,
            Key={'interaction_id': {'S': interaction_id}}
        )
        if 'Item' not in response:
            logger.error(f"Item not found in table {metadata_table_name}")
            return {
                'statusCode': 404,
                'body': f"Item not found in table {metadata_table_name}"
            }
        metadata=response['Item']
        agent_id = metadata['agent_id']['S']
        customer_id = metadata['customer_id']['S']
        call_duration = metadata['call_duration']['N']

        # create an item for the interaction table
        item = {
            'interaction_id': {'S': interaction_id},
            'agent_id': {'S': agent_id},
            'customer_id': {'S': customer_id},
            'call_duration': {'N': call_duration},
            'assigned_to': {'S': message_body['assigned_to']},
            'due_date': {'NULL': True} if message_body['due_date'] is None else {'S': message_body['due_date']},
            'topic': {'S': message_body['topic']},
            'satisfaction_score': {'N': str(message_body['satisfaction_score'])},
            'sentiment_analysis': {'S': message_body['sentiment_analysis']},
            'feedback_comments': {'S': message_body['feedback_comments']},
            'compliance_status': {'S': message_body['compliance_status']},
            'escalation_flag': {'BOOL': message_body['escalation_flag']},
            'escalation_reason': {'S': message_body['escalation_reason']},
            'agent_efficiency_score': {'N': str(message_body['agent_efficiency_score'])},
            'follow_up_flag': {'BOOL': message_body['follow_up_flag']},
            'follow_up_notes': {'S': message_body['follow_up_notes']},
        }

        dynamodb.put_item(
            TableName=interaction_table_name,
            Item=item
        )
        logger.info(f"Successfully added item to table {interaction_table_name}")



    except Exception as e:
        logger.error(f"An error occurred: {e}")
