import json
import os
from datetime import datetime
from unittest import mock

import boto3
import pytest
from moto import mock_rds, mock_s3, mock_secretsmanager

from ..file_parser_lambda import (
    IotData,
    LambdaError,
    filter_events,
    get_db_credentials,
    get_env_value,
    get_rds_endpoint,
    parse_s3_csv_file,
    write_to_rds,
)

def create_s3_bucket_with_object(body: str) -> tuple[str, str]:
    bucket_name = "test-bucket"
    bucket_object_key = "new_object_key"

    conn = boto3.resource("s3")
    bucket = conn.create_bucket(Bucket=bucket_name)
    bucket.put_object(Key=bucket_object_key, Body=body)
    return bucket_name, bucket_object_key



def test_filter_events__missing_event_details() -> None:
    valid_event = {"eventSource": "aws:s3", "eventName": "ObjectCreated:Put"}
    no_event_source = {"No": "eventSource", "eventName": "ObjectCreated:Put"}
    no_event_name = {"eventSource": "aws:s3", "No": "eventName"}

    assert filter_events({"No": "Records"}) == []

    events = filter_events({"Records": [no_event_source, valid_event]})
    assert events == [valid_event]

    events = filter_events({"Records": [no_event_name, valid_event]})
    assert events == [valid_event]


def test_filter_events__multiple_events() -> None:
    valid_event = {"eventSource": "aws:s3", "eventName": "ObjectCreated:Put"}
    valid_event_1 = {**valid_event, "s3": "1"}
    valid_event_2 = {**valid_event, "s3": "2"}
    invalid_event = {"eventSource": "aws:s3", "eventName": "Invalid"}

    events = filter_events({"Records": [valid_event_1, invalid_event, valid_event_2]})
    assert events == [valid_event_1, valid_event_2]


@mock_s3
def test_parse_s3_csv_file__s3_object_missing() -> None:
    bucket_name = "test-bucket"
    bucket_object_key = "new_object_key"

    conn = boto3.resource("s3")
    conn.create_bucket(Bucket=bucket_name)

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket_name, bucket_object_key)
    assert str(e.value) == (
        "Failed to retrieve 'new_object_key' object from 'test-bucket' bucket: "
        "An error occurred (NoSuchKey) when calling the GetObject operation: "
        "The specified key does not exist."
    )


@mock_s3
def test_parse_s3_csv_file__empty_content() -> None:
    bucket, object_key = create_s3_bucket_with_object("")

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert (
        str(e.value) == "The 'new_object_key' object from 'test-bucket' bucket is empty"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_content() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "heading1,heading2\nvalue1,value2"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 5 validation errors for IotData\n"
        "device_id\n"
        "  field required (type=value_error.missing)\n"
        "timestamp\n"
        "  field required (type=value_error.missing)\n"
        "temperature\n"
        "  field required (type=value_error.missing)\n"
        "humidity\n"
        "  field required (type=value_error.missing)\n"
        "hvac_status\n"
        "  field required (type=value_error.missing)"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_device_id() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_err,2023-07-26 00:00:00,22.5,55.0,on"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 1 validation error for IotData\n"
        "device_id\n"
        "  invalid device id format provided: device_err (type=value_error)"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_timestamp() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_002,2023-26-07 00:00:00,22.5,55.0,on"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 1 validation error for IotData\n"
        "timestamp\n"
        "  invalid datetime format (type=value_error.datetime)"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_temperature() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_002,2023-07-26 00:00:00,22.5c,55.0,on"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 1 validation error for IotData\n"
        "temperature\n"
        "  value is not a valid float (type=type_error.float)"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_humidity() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_002,2023-07-26 00:00:00,22.5,55.0%,on"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 1 validation error for IotData\n"
        "humidity\n"
        "  value is not a valid float (type=type_error.float)"
    )


@mock_s3
def test_parse_s3_csv_file__invalid_hvac_status() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_002,2023-07-26 00:00:00,22.5,55.0,n/a"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == (
        "Failed to parse data: 1 validation error for IotData\n"
        "hvac_status\n"
        "  value could not be parsed to a boolean (type=type_error.bool)"
    )


@mock_s3
def test_parse_s3_csv_file__missing_header() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity\n"
        "device_002,2023-07-26 00:00:00,22.5,55.0,on"
    )

    with pytest.raises(LambdaError) as e:
        parse_s3_csv_file(bucket, object_key)
    assert str(e.value) == "Data parsed without a header"


@mock_s3
def test_parse_s3_csv_file__given_example() -> None:
    bucket, object_key = create_s3_bucket_with_object(
        "device_id,timestamp,temperature,humidity,hvac_status\n"
        "device_001,2023-07-26 00:00:00,22.5,55.0,on\n"
        "device_001,2023-07-26 01:00:00,22.6,54.5,on\n"
        "device_001,2023-07-26 02:00:00,22.8,53.0,on\n"
        "device_001,2023-07-26 03:00:00,22.7,52.7,on\n"
        "device_001,2023-07-26 04:00:00,22.6,52.2,off\n"
        "device_002,2023-07-26 00:00:00,23.0,52.0,off\n"
        "device_002,2023-07-26 01:00:00,22.8,52.3,off\n"
        "device_002,2023-07-26 02:00:00,22.7,52.7,off\n"
        "device_002,2023-07-26 03:00:00,22.5,53.0,off\n"
        "device_002,2023-07-26 04:00:00,22.4,53.2,on\n"
        "device_003,2023-07-26 00:00:00,22.2,55.2,on\n"
        "device_003,2023-07-26 01:00:00,22.1,55.6,on\n"
        "device_003,2023-07-26 02:00:00,22.0,56.0,on\n"
        "device_003,2023-07-26 03:00:00,22.1,56.2,on\n"
        "device_003,2023-07-26 04:00:00,22.2,56.5,off\n"
    )

    data = parse_s3_csv_file(bucket, object_key)
    data_values = [d.get_values() for d in data]
    assert data_values == [
        (1, 1690322400, 22.5, 55.0, True),
        (1, 1690326000, 22.6, 54.5, True),
        (1, 1690329600, 22.8, 53.0, True),
        (1, 1690333200, 22.7, 52.7, True),
        (1, 1690336800, 22.6, 52.2, False),
        (2, 1690322400, 23.0, 52.0, False),
        (2, 1690326000, 22.8, 52.3, False),
        (2, 1690329600, 22.7, 52.7, False),
        (2, 1690333200, 22.5, 53.0, False),
        (2, 1690336800, 22.4, 53.2, True),
        (3, 1690322400, 22.2, 55.2, True),
        (3, 1690326000, 22.1, 55.6, True),
        (3, 1690329600, 22.0, 56.0, True),
        (3, 1690333200, 22.1, 56.2, True),
        (3, 1690336800, 22.2, 56.5, False),
    ]


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


def test_write_to_rds__no_connection() -> None:
    iot_data = IotData(
        device_id="device_001",
        timestamp=datetime.now(),
        temperature=20.1,
        humidity=50.5,
        hvac_status=True,
    )
    with pytest.raises(LambdaError) as e:
        write_to_rds([iot_data], "127.0.0.1", "database", "user", "password", "table")
    assert str(e.value) == (
        "Failed to connect to RDS database: (2003, \"Can't connect to MySQL "
        "server on '127.0.0.1' ([Errno 111] Connection refused)\")"
    )


def test_write_to_rds__no_data() -> None:
    write_to_rds([], "127.0.0.1", "database", "user", "password", "table")

    with mock.patch(
        "file_parser_lambda.file_parser_lambda.pymysql.connect"
    ) as mock_connect:
        assert mock_connect.call_count == 0


def test_write_to_rds() -> None:
    with mock.patch(
        "file_parser_lambda.file_parser_lambda.pymysql.connect"
    ) as mock_connect:
        mock_executemany = mock.MagicMock(name="executemany")

        mock_cur = mock.MagicMock(name="cursor")
        mock_cur.rowcount = 1
        mock_cur.executemany = mock_executemany

        mock_conn = mock.MagicMock(name="connection")
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_connect.return_value.__enter__.return_value = mock_conn

        iot_data = IotData(
            device_id="device_001",
            timestamp=datetime.now(),
            temperature=20.1,
            humidity=50.5,
            hvac_status=True,
        )
        write_to_rds(
            [iot_data],
            "host",
            "database",
            "user",
            "password",
            "table",
        )

        assert mock_connect.call_args.kwargs == {
            "database": "database",
            "host": "host",
            "password": "password",
            "user": "user",
        }

        assert mock_executemany.call_args.args == (
            "INSERT INTO table (device_id,timestamp,temperature,humidity,hvac_status) VALUES (%s,%s,%s,%s,%s);",
            [iot_data.get_values()],
        )


