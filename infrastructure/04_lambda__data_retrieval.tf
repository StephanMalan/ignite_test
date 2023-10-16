################################################################################
# Lambda function that retrieves Iot data from RDS
################################################################################

resource "aws_lambda_function" "data_retrieval_lambda" {
  description      = "Create a lambda function that retrieves Iot data from RDS"
  function_name    = "data_retrieval_lambda"
  filename         = data.archive_file.data_retrieval_lambda_zip.output_path
  source_code_hash = data.archive_file.data_retrieval_lambda_zip.output_base64sha256
  role             = aws_iam_role.data_retrieval_lambda_role.arn
  handler          = "data_retrieval_lambda.handler"
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

data "archive_file" "data_retrieval_lambda_zip" {
  type        = "zip"
  source_dir  = "../data_retrieval_lambda/package"
  output_path = "../data_retrieval_lambda/package.zip"
}

resource "aws_iam_role" "data_retrieval_lambda_role" {
  name = "data_retrieval_lambda_role"
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

resource "aws_iam_policy_attachment" "data_retrieval_lambda_policy_basic_attch" {
  name       = "data_retrieval_lambda_policy_basic_attch"
  roles      = [aws_iam_role.data_retrieval_lambda_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy" "data_retrieval_lambda_policy" {
  description = "IAM policy for data retrieval lambda"
  name        = "data_retrieval_lambda_policy"
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
          "rds:DescribeDBInstances"
        ],
        Resource = "*"
      },
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

resource "aws_iam_policy_attachment" "data_retrieval_lambda_policy_attch" {
  name       = "data_retrieval_lambda_policy_attch"
  roles      = [aws_iam_role.data_retrieval_lambda_role.name]
  policy_arn = aws_iam_policy.data_retrieval_lambda_policy.arn
}


