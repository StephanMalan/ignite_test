#!/bin/bash

cd "$(dirname "$0")"

poetry run coverage run --source=data_retrieval_lambda --omit=*/tests/* -m pytest tests -vv
poetry run coverage report --show-missing --skip-empty
