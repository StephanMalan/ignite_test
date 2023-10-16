import json
import os

import boto3
import pymysql


def get_host(mysql_id: str, region: str) -> str:
    print("Retrieving RDS endpoint")
    rds_client = boto3.client("rds", region_name=region)
    response = rds_client.describe_db_instances(DBInstanceIdentifier=mysql_id)
    return response["DBInstances"][0]["Endpoint"]["Address"]


def get_db_credentials(secret_manager_id: str, region: str) -> tuple[str, str]:
    print("Retrieving RDS credentials")
    secret_client = boto3.client("secretsmanager", region_name=region)
    resp = secret_client.get_secret_value(SecretId=secret_manager_id)
    secrets = json.loads(resp["SecretString"])
    return (secrets["mysql_user"], secrets["mysql_password"])


REGION = os.environ["TF_VAR_REGION"]
SECRET_MANAGER_ID = os.environ["TF_VAR_SECRET_MANAGER_ID"]
MYSQL_ID = os.environ["TF_VAR_DATA_MYSQL_ID"]
MYSQL_HOST = get_host(MYSQL_ID, REGION)
MYSQL_USER, MYSQL_PASSWORD = get_db_credentials(SECRET_MANAGER_ID, REGION)
MYSQL_DATABASE = os.environ["TF_VAR_DATA_MYSQL_DATABASE"]
MYSQL_TABLE = os.environ["TF_VAR_DATA_MYSQL_TABLE"]


print(f"Connecting to: {MYSQL_HOST}")
conn = pymysql.connect(
    host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, charset="utf8mb4"
)
cur = conn.cursor()
print(f"Creating '{MYSQL_DATABASE}' database if it doesn't exist")
cur.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")

conn = pymysql.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset="utf8mb4",
)
cur = conn.cursor()
print(f"Creating '{MYSQL_TABLE}' table if it doesn't exist")
cur.execute(
    f"""
    CREATE TABLE IF NOT EXISTS {MYSQL_TABLE} (
        device_id int,
        timestamp int,
        temperature float,
        humidity float,
        hvac_status boolean,
        PRIMARY KEY (device_id, timestamp)
    );
    """
)
