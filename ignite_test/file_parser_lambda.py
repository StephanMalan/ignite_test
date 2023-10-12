from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from aws_lambda_typing import context as context_
    from aws_lambda_typing import events


def handler(events: "events.SQSEvent", context: "context_.Context") -> None:
    s3 = boto3.client("s3")

    for event in events["Records"]:
        if event["eventSource"] != "aws:s3" or event["eventName"] != "ObjectCreated:Put":
            continue
        s3_bucket = event["s3"]["bucket"]["name"]
        s3_object_name = event["s3"]["object"]["key"]
        s3_object = s3.get_object(Bucket=s3_bucket, Key=s3_object_name)
        content = s3_object["Body"].read().decode("utf-8")
        print(content)
