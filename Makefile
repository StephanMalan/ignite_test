run:
	poetry run python -m ignite_test.main

test:
	poetry run coverage run --source=ignite_test -m pytest -vv && poetry run coverage report --show-missing --skip-empty

lint:
	poetry run ruff ./ && poetry run pylint ./ignite_test && poetry run mypy . --explicit-package-bases
