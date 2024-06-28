# Environment variables for the SAM application
export ENVIRONMENT="dev"
export PROJECT="AudioProcessingProject"
export VERSION="1.0.0"

# S3 bucket for packaging the SAM application
export S3_BUCKET="sam-packaging-bucket"

# Stack name for the CloudFormation stack
export STACK_NAME="audio-processing-stack"

# Path to the prompt file to upload
export PROMPT_FILE="prompts/template.txt"

# S3 bucket for transcription results as per your SAM template
export TRANSCRIPTION_BUCKET="transcription-result-bucket"
