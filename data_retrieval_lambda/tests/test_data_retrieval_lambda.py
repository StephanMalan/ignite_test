import json
import os
from unittest import mock

import boto3
import pytest
from moto import mock_rds, mock_secretsmanager
from pydantic import ValidationError

from ..data_retrieval_lambda import (
    LambdaError,
    get_db_credentials,
    get_env_value,
    get_rds_endpoint,
    read_from_rds,
    validate_event,
)


def test_validate_event__wrong_resource() -> None:
    with pytest.raises(ValidationError) as e:
        validate_event(
            {
                "resource": "/another-endpoint",
                "httpMethod": "GET",
                "queryStringParameters": {
                    "device_id": 1,
                    "datetime_from": 1,
                    "datetime_to": 1,
                },
            }
        )
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "resource\n"
        "  unexpected value; permitted: '/data' (type=value_error.const; "
        "given=/another-endpoint; permitted=('/data',))"
    )


def test_validate_event__wrong_method() -> None:
    with pytest.raises(ValidationError) as e:
        validate_event(
            {
                "resource": "/data",
                "httpMethod": "POST",
                "queryStringParameters": {
                    "device_id": 1,
                    "datetime_from": 1,
                    "datetime_to": 1,
                },
            }
        )
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "httpMethod\n"
        "  unexpected value; permitted: 'GET' (type=value_error.const; "
        "given=POST; permitted=('GET',))"
    )


def test_validate_event__invalid_device_id() -> None:
    event = {
        "resource": "/data",
        "httpMethod": "GET",
        "queryStringParameters": {
            "datetime_from": 1,
            "datetime_to": 1,
        },
    }

    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> device_id\n"
        "  field required (type=value_error.missing)"
    )

    event["queryStringParameters"]["device_id"] = "string"
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> device_id\n"
        "  value is not a valid integer (type=type_error.integer)"
    )

    event["queryStringParameters"]["device_id"] = -1
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> device_id\n"
        "  ensure this value is greater than or equal to 0 "
        "(type=value_error.number.not_ge; limit_value=0)"
    )

    event["queryStringParameters"]["device_id"] = 1000
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> device_id\n"
        "  ensure this value is less than or equal to 999 "
        "(type=value_error.number.not_le; limit_value=999)"
    )


def test_validate_event__invalid_datetime_from() -> None:
    event = {
        "resource": "/data",
        "httpMethod": "GET",
        "queryStringParameters": {
            "device_id": 1,
            "datetime_to": 1,
        },
    }

    event["queryStringParameters"]["datetime_from"] = "string"
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_from\n"
        "  value is not a valid integer (type=type_error.integer)"
    )

    event["queryStringParameters"]["datetime_from"] = -1
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_from\n"
        "  ensure this value is greater than or equal to 0 "
        "(type=value_error.number.not_ge; limit_value=0)"
    )

    event["queryStringParameters"]["datetime_from"] = 2147483648
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_from\n"
        "  ensure this value is less than or equal to 2147483647 "
        "(type=value_error.number.not_le; limit_value=2147483647)"
    )


def test_validate_event__invalid_datetime_to() -> None:
    event = {
        "resource": "/data",
        "httpMethod": "GET",
        "queryStringParameters": {
            "device_id": 1,
            "datetime_from": 1,
        },
    }

    event["queryStringParameters"]["datetime_to"] = "string"
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_to\n"
        "  value is not a valid integer (type=type_error.integer)"
    )

    event["queryStringParameters"]["datetime_to"] = -1
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_to\n"
        "  ensure this value is greater than or equal to 0 "
        "(type=value_error.number.not_ge; limit_value=0)"
    )

    event["queryStringParameters"]["datetime_to"] = 2147483648
    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> datetime_to\n"
        "  ensure this value is less than or equal to 2147483647 "
        "(type=value_error.number.not_le; limit_value=2147483647)"
    )


def test_validate_event__ensure_at_least_one_date_present() -> None:
    event = {
        "resource": "/data",
        "httpMethod": "GET",
        "queryStringParameters": {
            "device_id": 1,
        },
    }

    with pytest.raises(ValidationError) as e:
        validate_event(event)
    assert str(e.value) == (
        "1 validation error for ApiGatewayEvent\n"
        "queryStringParameters -> __root__\n"
        "  ensure either 'datetime_from', 'datetime_to', or both is present (type=value_error)"
    )


def test_get_env_value__missing() -> None:
    env_key = "TEST_ENV_KEY"
    os.environ[env_key] = ""
    with pytest.raises(LambdaError) as e:
        get_env_value(env_key)
    assert str(e.value) == "Failed to retrieve 'TEST_ENV_KEY' environment variable"


def test_get_env_value() -> None:
    env_key = "TEST_ENV_KEY"
    env_val = "TEST_ENV_VALUE"
    os.environ[env_key] = env_val
    assert get_env_value(env_key) == env_val


@mock_rds
def test_get_rds_endpoint__missing_rds_instance() -> None:
    region = "us-west-1"

    with pytest.raises(LambdaError) as e:
        print(get_rds_endpoint("wrong_rds_id", region))
    assert str(e.value) == (
        "Failed to retrieve 'wrong_rds_id' RDS instance: An error occurred "
        "(DBInstanceNotFound) when calling the DescribeDBInstances operation: "
        "DBInstance wrong_rds_id not found."
    )


@mock_rds
def test_get_rds_endpoint() -> None:
    region = "us-west-1"
    rds_id = "test"
    conn = boto3.client("rds", region_name=region)
    conn.create_db_instance(
        DBInstanceIdentifier=rds_id,
        DBInstanceClass="db.t2.micro",
        Engine="mysql",
        PubliclyAccessible=False,
    )

    assert (
        get_rds_endpoint(rds_id, region)
        == "test.aaaaaaaaaa.us-west-1.rds.amazonaws.com"
    )


@mock_secretsmanager
def test_get_db_credentials__missing_secrets_manager() -> None:
    with pytest.raises(LambdaError) as e:
        get_db_credentials("missing_secrets_manager", "us-west-1")
    assert str(e.value) == (
        "Failed to retrieve secret manager 'missing_secrets_manager': "
        "An error occurred (ResourceNotFoundException) when calling the "
        "GetSecretValue operation: Secrets Manager can't find the specified secret."
    )


@mock_secretsmanager
def test_get_db_credentials__non_key_value() -> None:
    region = "us-west-1"
    secret_manager_id = "test_secrets"
    conn = boto3.client("secretsmanager", region_name=region)
    conn.create_secret(Name=secret_manager_id)
    conn.put_secret_value(SecretId=secret_manager_id, SecretString="single_secret")

    with pytest.raises(LambdaError) as e:
        get_db_credentials(secret_manager_id, region)
    assert str(e.value) == (
        "Failed to retrieve credentials from secret manager 'test_secrets': "
        "Expecting value: line 1 column 1 (char 0)"
    )


@mock_secretsmanager
def test_get_db_credentials__missing_username() -> None:
    region = "us-west-1"
    secret_manager_id = "test_secrets"
    conn = boto3.client("secretsmanager", region_name=region)
    conn.create_secret(Name=secret_manager_id)
    conn.put_secret_value(
        SecretId=secret_manager_id,
        SecretString=json.dumps({"mysql_password": "password"}),
    )

    with pytest.raises(LambdaError) as e:
        get_db_credentials(secret_manager_id, region)
    assert str(e.value) == (
        "Failed to retrieve credentials from secret manager 'test_secrets': 'mysql_user'"
    )


@mock_secretsmanager
def test_get_db_credentials__missing_password() -> None:
    region = "us-west-1"
    secret_manager_id = "test_secrets"
    conn = boto3.client("secretsmanager", region_name=region)
    conn.create_secret(Name=secret_manager_id)
    conn.put_secret_value(
        SecretId=secret_manager_id,
        SecretString=json.dumps({"mysql_user": "user"}),
    )

    with pytest.raises(LambdaError) as e:
        get_db_credentials(secret_manager_id, region)
    assert str(e.value) == (
        "Failed to retrieve credentials from secret manager 'test_secrets': 'mysql_password'"
    )


@mock_secretsmanager
def test_get_db_credentials() -> None:
    region = "us-west-1"
    secret_manager_id = "test_secrets"
    conn = boto3.client("secretsmanager", region_name=region)
    conn.create_secret(Name=secret_manager_id)
    conn.put_secret_value(
        SecretId=secret_manager_id,
        SecretString=json.dumps({"mysql_user": "user", "mysql_password": "password"}),
    )

    assert get_db_credentials(secret_manager_id, region) == ("user", "password")


def test_read_from_rds__no_connection() -> None:
    with pytest.raises(LambdaError) as e:
        read_from_rds("127.0.0.1", "database", "user", "password", "table", 1, 1, 1)
    assert str(e.value) == (
        "Failed to connect to RDS database: (2003, \"Can't connect to MySQL "
        "server on '127.0.0.1' ([Errno 111] Connection refused)\")"
    )


def test_read_from_rds__no_datetime_from() -> None:
    with mock.patch(
        "data_retrieval_lambda.data_retrieval_lambda.pymysql.connect"
    ) as mock_connect:
        output = {"test": "output"}
        mock_execute = mock.MagicMock(name="execute")
        mock_cur = mock.MagicMock(name="cursor")
        mock_cur.execute = mock_execute
        mock_cur.fetchall.return_value = output
        mock_conn = mock.MagicMock(name="connection")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_connect.return_value.__enter__.return_value = mock_conn

        data = read_from_rds(
            "host", "database", "user", "password", "table", 1, None, 3
        )
        assert data == output

        assert mock_connect.call_args.kwargs == {
            "database": "database",
            "host": "host",
            "password": "password",
            "user": "user",
        }

        assert mock_execute.call_args.args == (
            "SELECT * FROM table WHERE device_id = %s AND timestamp < %s",
            (1, 3),
        )


def test_read_from_rds__no_datetime_to() -> None:
    with mock.patch(
        "data_retrieval_lambda.data_retrieval_lambda.pymysql.connect"
    ) as mock_connect:
        output = {"test": "output"}
        mock_execute = mock.MagicMock(name="execute")
        mock_cur = mock.MagicMock(name="cursor")
        mock_cur.execute = mock_execute
        mock_cur.fetchall.return_value = output
        mock_conn = mock.MagicMock(name="connection")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_connect.return_value.__enter__.return_value = mock_conn

        data = read_from_rds(
            "host", "database", "user", "password", "table", 1, 2, None
        )
        assert data == output

        assert mock_connect.call_args.kwargs == {
            "database": "database",
            "host": "host",
            "password": "password",
            "user": "user",
        }

        assert mock_execute.call_args.args == (
            "SELECT * FROM table WHERE device_id = %s AND timestamp >= %s",
            (1, 2),
        )


def test_read_from_rds() -> None:
    with mock.patch(
        "data_retrieval_lambda.data_retrieval_lambda.pymysql.connect"
    ) as mock_connect:
        output = {"test": "output"}
        mock_execute = mock.MagicMock(name="execute")
        mock_cur = mock.MagicMock(name="cursor")
        mock_cur.execute = mock_execute
        mock_cur.fetchall.return_value = output
        mock_conn = mock.MagicMock(name="connection")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_connect.return_value.__enter__.return_value = mock_conn

        data = read_from_rds("host", "database", "user", "password", "table", 1, 2, 3)
        assert data == output

        assert mock_connect.call_args.kwargs == {
            "database": "database",
            "host": "host",
            "password": "password",
            "user": "user",
        }

        assert mock_execute.call_args.args == (
            "SELECT * FROM table WHERE device_id = %s AND timestamp >= %s AND timestamp < %s",
            (1, 2, 3),
        )
