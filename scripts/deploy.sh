#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Load environment variables from setup.env
source setup.env

# Build the SAM application
echo "Building the SAM application..."
sam build

# Package the SAM application
echo "Packaging the SAM application..."
sam package --output-template-file packaged.yaml --s3-bucket $S3_BUCKET

# Deploy the SAM application
echo "Deploying the SAM application..."
sam deploy --template-file packaged.yaml --stack-name $STACK_NAME --capabilities CAPABILITY_IAM --parameter-overrides Environment=$ENVIRONMENT Project=$PROJECT Version=$VERSION

# Upload the prompt file to the TranscriptionBucket
if [ -f "$PROMPT_FILE" ]; then
  echo "Uploading prompt file to S3..."
  aws s3 cp $PROMPT_FILE s3://$TRANSCRIPTION_BUCKET/template.txt
else
  echo "Prompt file not found: $PROMPT_FILE"
fi

# Get the API Gateway endpoint URL
api_url=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='AudioProcessingApi'].OutputValue" --output text)

echo "Deployment completed successfully!"
echo "API Gateway endpoint URL: $api_url"

