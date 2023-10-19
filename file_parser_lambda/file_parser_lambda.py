"""
Python script that is called by Lambda function when an object is put in S3.

This script:
 - Gets triggered by a new .txt object added to the configured S3 bucket.
 - Reads the content of the new object.
 - Parser the csv and validates the content.
 - Writes the data to a configures MySQL RDS instance.
"""

import csv
import json
import os
import re
from datetime import datetime
from typing import Any

import boto3
import pymysql
from aws_lambda_powertools.utilities.parser import BaseModel, ValidationError, validator
from botocore.exceptions import ClientError


class LambdaError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class IotData(BaseModel):
    """Pydantic model for validating and transforming IoT data"""

    device_id: int
    timestamp: datetime
    temperature: float
    humidity: float
    hvac_status: bool

    @validator("device_id", pre=True)
    @classmethod
    def device_id_validator(cls, value: str) -> int:
        """Custom validator for device_id"""
        match_obj = re.match(r"^device_([0-9]{3})$", value)
        if not match_obj:
            raise ValueError(f"invalid device id format provided: {value}")
        return int(match_obj.group(1))

    def get_values(self) -> tuple[Any]:
        """Returns the values of the object in fixed order"""
        values = []
        for field_name in IotData.__fields__:
            if field_name == "timestamp":
                values.append(int(self.timestamp.timestamp()))
            else:
                values.append(getattr(self, field_name))
        return tuple(values)


def handler(events: Any, _context: Any) -> None:
    """Handler function that is called by AWS Lambda"""
    secret_manager_id = get_env_value("SECRET_MANAGER_ID")
    region = get_env_value("REGION")
    rds_id = get_env_value("MYSQL_ID")
    database = get_env_value("MYSQL_DATABASE")
    table = get_env_value("MYSQL_TABLE")

    for event in filter_events(events):
        s3_bucket = event["s3"]["bucket"]["name"]
        s3_object_key = event["s3"]["object"]["key"]

        data = parse_s3_csv_file(s3_bucket, s3_object_key)
        host = get_rds_endpoint(rds_id, region)
        user, password = get_db_credentials(secret_manager_id, region)

        write_to_rds(data, host, database, user, password, table)


def filter_events(events: Any) -> list[dict[str, Any]]:
    """Filters provided events to only include new objects created on S3"""
    if "Records" not in events:
        return []
    return [
        event
        for event in events["Records"]
        if "eventSource" in event
        and event["eventSource"] == "aws:s3"
        and "eventName" in event
        and event["eventName"] == "ObjectCreated:Put"
    ]


def parse_s3_csv_file(s3_bucket: str, s3_object_key: str) -> list[IotData]:
    """Read csv content from S3 object then parse and validate the values"""
    print(f"Reading '{s3_object_key}' object from '{s3_bucket}'")
    s3_client = boto3.client("s3")
    try:
        s3_object = s3_client.get_object(Bucket=s3_bucket, Key=s3_object_key)
    except ClientError as e:
        raise LambdaError(
            f"Failed to retrieve '{s3_object_key}' object from '{s3_bucket}' bucket: {e}"
        ) from e
    content = s3_object["Body"].read().decode("utf-8")
    if not content.strip():
        raise LambdaError(
            f"The '{s3_object_key}' object from '{s3_bucket}' bucket is empty"
        )
    csv_reader = csv.DictReader(content.strip().split("\n"))
    csv_data = list(csv_reader)
    if any(None in d for d in csv_data):
        raise LambdaError("Data parsed without a header")
    try:
        data = [IotData(**d) for d in csv_data]
    except ValidationError as e:
        raise LambdaError(f"Failed to parse data: {str(e)}") from e
    return data


def get_env_value(env_var: str) -> str:
    """Retrieve environment value"""
    value = os.environ.get(env_var)
    if not value:
        raise LambdaError(f"Failed to retrieve '{env_var}' environment variable")
    return value


def get_rds_endpoint(rds_id: str, region: str) -> str:
    """Retrieves the ARN of the RDS instance"""
    print("Retrieving RDS ARN")
    rds_client = boto3.client("rds", region_name=region)
    try:
        response = rds_client.describe_db_instances(DBInstanceIdentifier=rds_id)
    except ClientError as e:
        raise LambdaError(f"Failed to retrieve '{rds_id}' RDS instance: {e}") from e
    try:
        endpoint = response["DBInstances"][0]["Endpoint"]["Address"]
    except (KeyError, IndexError) as e:
        raise LambdaError(
            f"Failed to retrieve endpoint for '{rds_id} 'RDS instance: {e}"
        ) from e
    return endpoint


def get_db_credentials(secret_manager_id: str, region: str) -> tuple[str, str]:
    """Retrieve the RDS instance username and password from the Secret Manager"""
    print("Retrieving RDS credentials")
    secret_client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = secret_client.get_secret_value(SecretId=secret_manager_id)
    except ClientError as e:
        raise LambdaError(
            f"Failed to retrieve secret manager '{secret_manager_id}': {e}"
        ) from e
    try:
        secrets = json.loads(resp["SecretString"])
        credentials = (secrets["mysql_user"], secrets["mysql_password"])
    except (KeyError, json.JSONDecodeError) as e:
        raise LambdaError(
            f"Failed to retrieve credentials from secret manager '{secret_manager_id}': {e}"
        ) from e
    return credentials


def write_to_rds(
    data: list[IotData], host: str, database: str, user: str, password: str, table: str
):
    """Write Iot data to the RDS instance"""
    print("Connecting to RDS")
    if not data:
        print("No data to write")
        return
    try:
        with pymysql.connect(
            host=host, user=user, password=password, database=database
        ) as conn:
            fields_to_insert = list(IotData.__fields__.keys())
            select_statement = (
                f"INSERT INTO {table} ({','.join(fields_to_insert)}) "
                f"VALUES ({','.join(['%s'] * len(fields_to_insert))});"
            )
            print("Inserting data")
            with conn.cursor() as cur:
                cur.executemany(select_statement, [d.get_values() for d in data])
                conn.commit()
                print(f"Successfully inserted {cur.rowcount} row(s) of data")
    except pymysql.err.OperationalError as e:
        raise LambdaError(f"Failed to connect to RDS database: {e}") from e
