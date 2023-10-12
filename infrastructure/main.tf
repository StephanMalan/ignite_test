provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "file_upload" {
  bucket        = "ignite-test-file-upload-bucket"
  force_destroy = true
}

data "archive_file" "file_parser_lambda_zip" {
  type        = "zip"
  source_file = "../ignite_test/file_parser_lambda.py"
  output_path = "../ignite_test/file_parser_lambda.zip"
}

resource "aws_lambda_function" "file_parser_lambda" {
  function_name = "file_parser_lambda"
  description   = "Create a lambda function that parses files as they are uploaded to S3"
  filename      = data.archive_file.file_parser_lambda_zip.output_path
  role          = aws_iam_role.file_parser_lambda_role.arn
  handler       = "file_parser_lambda.handler"
  runtime       = "python3.10"
}

resource "aws_s3_bucket_notification" "file_upload_notification" {
  bucket = aws_s3_bucket.file_upload.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.file_parser_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".txt"
  }
}
