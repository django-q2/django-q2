#!/bin/bash
# Note that this file needs to have the executable bit set for it to work with later localstack implementations.

export DEFAULT_REGION=us-west-2

create_sqs() {
    QUEUE_NAME="$1"
    TIMEOUT=${2:-60}
    DL_QUEUE_URL=$(awslocal sqs create-queue --queue-name "dl-$QUEUE_NAME" --query QueueUrl --output text)
    echo ">>> Created $DL_QUEUE_URL queue!"
    DL_QUEUE_ARN=$(awslocal sqs get-queue-attributes --queue-url "$DL_QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
    awslocal sqs create-queue --queue-name "$QUEUE_NAME" --attributes '{
        "RedrivePolicy": "{\"deadLetterTargetArn\": \"'"$DL_QUEUE_ARN"'\",\"maxReceiveCount\":\"3\"}",
        "VisibilityTimeout": "'"$TIMEOUT"'"
    }'
}

# Create SQS queues
create_sqs testing