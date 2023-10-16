#!/bin/bash

cd "$(dirname "$0")"

poetry run coverage run --source=file_parser_lambda --omit=*/tests/* -m pytest tests -vv
poetry run coverage report --show-missing --skip-empty
