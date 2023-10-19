include .env
export

test_lambda:
	sh file_parser_lambda/test.sh
	sh data_retrieval_lambda/test.sh

lint:
	poetry run ruff ./ignite_test
	poetry run pylint ./ignite_test
	poetry run mypy ./ignite_test --explicit-package-bases
	poetry run ruff ./file_parser_lambda
	poetry run pylint ./file_parser_lambda
	poetry run mypy ./file_parser_lambda --explicit-package-bases
	poetry run ruff ./data_retrieval_lambda
	poetry run pylint ./data_retrieval_lambda
	poetry run mypy ./data_retrieval_lambda --explicit-package-bases

terra_init:
	terraform -chdir=infrastructure init

terra_apply: prepare_lambda
	terraform -chdir=infrastructure apply

terra_plan: prepare_lambda
	terraform -chdir=infrastructure plan

terra_destroy:
	terraform -chdir=infrastructure destroy

setup_mysql:
	sh setup_sql/run.sh

prepare_lambda:
	sh file_parser_lambda/prepare.sh
	sh data_retrieval_lambda/prepare.sh

