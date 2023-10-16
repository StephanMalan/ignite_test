"""
Python script that is called by Lambda function when request is sent to API Gateway.

This script:
 - Gets triggered by "GET /data" endpoint in API Gateway.
 - Reads data from RDS based on provided query parameters.
"""

import json
import os
from typing import Any, Literal

import boto3
import pymysql
from aws_lambda_powertools.utilities.parser import (
    BaseModel,
    Field,
    ValidationError,
    parse,
    root_validator,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError


class LambdaError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class QueryParameters(BaseModel):
    """Model to validate query parameters"""

    device_id: int = Field(ge=0, le=999)
    datetime_from: int | None = Field(ge=0, le=2147483647)
    datetime_to: int | None = Field(ge=0, le=2147483647)

    @root_validator
    @classmethod
    def validate_datetimes(cls, values: dict[str, Any]) -> dict[str, Any]:
        if not values.get("datetime_from") and not values.get("datetime_to"):
            raise ValueError(
                "ensure either 'datetime_from', 'datetime_to', or both is present"
            )
        return values


class ApiGatewayEvent(BaseModel):
    """Model to validate parameters sent by API Gateway"""

    resource: Literal["/data"]
    httpMethod: Literal["GET"]
    queryStringParameters: QueryParameters


def handler(event: Any, _context: LambdaContext) -> dict[str, Any]:
    """Handler function that is called by AWS Lambda"""
    try:
        api_event = validate_event(event)
        secret_manager_id = get_env_value("SECRET_MANAGER_ID")
        region = get_env_value("REGION")
        rds_id = get_env_value("MYSQL_ID")
        database = get_env_value("MYSQL_DATABASE")
        table = get_env_value("MYSQL_TABLE")

        host = get_rds_endpoint(rds_id, region)
        user, password = get_db_credentials(secret_manager_id, region)

        device_id = api_event.queryStringParameters.device_id
        datetime_from = api_event.queryStringParameters.datetime_from
        datetime_to = api_event.queryStringParameters.datetime_to
        results = read_from_rds(
            host, database, user, password, table, device_id, datetime_from, datetime_to
        )
        return {"statusCode": 200, "body": json.dumps({"results": results})}
    except ValidationError as e:
        return {"statusCode": 400, "body": json.dumps({"errors": e.errors()})}


def validate_event(event: Any) -> ApiGatewayEvent:
    return parse(event=event, model=ApiGatewayEvent)


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


def read_from_rds(
    host: str,
    database: str,
    user: str,
    password: str,
    table: str,
    device_id: int,
    datetime_from: int | None,
    datetime_to: int | None,
) -> dict[str, Any]:
    """Read Iot data from the RDS instance"""
    print("Connecting to RDS")
    try:
        with pymysql.connect(
            host=host, user=user, password=password, database=database
        ) as conn:
            statement_variables = [device_id]
            statement = f"SELECT * FROM {table} WHERE device_id = %s"
            if datetime_from:
                statement += " AND timestamp >= %s"
                statement_variables.append(datetime_from)
            if datetime_to:
                statement += " AND timestamp < %s"
                statement_variables.append(datetime_to)

            with conn.cursor(pymysql.cursors.DictCursor) as curr:
                print(curr, curr.execute)
                curr.execute(statement, tuple(statement_variables))
                return curr.fetchall()
    except pymysql.err.OperationalError as e:
        raise LambdaError(f"Failed to connect to RDS database: {e}") from e
