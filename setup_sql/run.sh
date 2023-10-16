#!/bin/bash

cd "$(dirname "$0")"

poetry run python -m create_mysql_schema
