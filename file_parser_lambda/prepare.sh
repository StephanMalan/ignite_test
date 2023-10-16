#!/bin/bash

set -e

cd "$(dirname "$0")"

rm -rf package
pip install -q -t package .
