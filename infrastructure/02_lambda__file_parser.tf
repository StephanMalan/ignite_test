################################################################################
# Lambda function that parses S3 csv files and writes to MySQL RDS instance
################################################################################

resource "aws_lambda_function" "file_parser_lambda" {
  description      = "Create a lambda function that parses files as they are uploaded to S3"
  function_name    = "file_parser_lambda"
  filename         = data.archive_file.file_parser_lambda_zip.output_path
  source_code_hash = base64sha256(file("../file_parser_lambda/file_parser_lambda.py"))
  role             = aws_iam_role.file_parser_lambda_role.arn
  handler          = "file_parser_lambda.handler"
  runtime          = "python3.10"
  timeout          = 15
  layers           = ["arn:aws:lambda:us-west-1:017000801446:layer:AWSLambdaPowertoolsPythonV2:43"]
  environment {
    variables = {
      SECRET_MANAGER_ID = var.SECRET_MANAGER_ID
      REGION            = var.REGION
      MYSQL_ID          = var.DATA_MYSQL_ID
      MYSQL_DATABASE    = var.DATA_MYSQL_DATABASE
      MYSQL_TABLE       = var.DATA_MYSQL_TABLE
    }
  }
}

data "archive_file" "file_parser_lambda_zip" {
  type        = "zip"
  source_dir  = "../file_parser_lambda/package"
  output_path = "../file_parser_lambda/package.zip"
}

resource "aws_iam_role" "file_parser_lambda_role" {
  name = "file_parser_lambda_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Action = "sts:AssumeRole",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy_attachment" "file_parser_lambda_policy_basic_attch" {
  name       = "file_parser_lambda_policy_basic_attch"
  roles      = [aws_iam_role.file_parser_lambda_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "file_parser_lambda_policy" {
  name        = "file_parser_lambda_policy"
  description = "IAM policy for file parser lambda"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream"
        ],
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = "${aws_s3_bucket.file_upload_bucket.arn}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "rds:DescribeDBInstances"
        ],
        Resource = "*"
      }
      ,
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = aws_secretsmanager_secret.acme_secrets.arn
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "file_parser_lambda_policy_attch" {
  name       = "file_parser_lambda_policy_attch"
  roles      = [aws_iam_role.file_parser_lambda_role.name]
  policy_arn = aws_iam_policy.file_parser_lambda_policy.arn
}

resource "aws_cloudwatch_log_group" "file_parser_lambda_log_group" {
  name              = "/aws/lambda/${aws_lambda_function.file_parser_lambda.function_name}"
  retention_in_days = 7
}
