# data "aws_iam_policy_document" "lambda_assum_role_policy"{
#   statement {
#     effect  = "Allow"
#     actions = ["sts:AssumeRole"]
#     principals {
#       type        = "Service"
#       identifiers = ["lambda.amazonaws.com"]
#     }
#   }
# }

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

# resource "aws_iam_role" "file_upload_role" {
#   name = "file_upload_role"
#   assume_role_policy = jsondecode({
#     Version = "2012-10-17"
#     Statement = [{
#       Effect = "Allow"
#       Action = "lambda:InvokeFunction"
#     }]
#   })
# }

resource "aws_lambda_permission" "file_upload_lambda_permission" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.file_parser_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.file_upload.arn
}

resource "aws_iam_policy" "file_parser_lambda_policy" {
  name        = "file_parser_lambda_policy"
  description = "IAM policy for file parser lambda"
  # policy = {
  #   "Version": "2012-10-17",
  #   "Statement": [{
  #     "Effect": "Allow",
  #     "Action": [
  #       "s3."
  #     ]
  #     "Resource": ""
  #   }]
  # }
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
          "s3:GetObject"
        ],
        Resource = aws_s3_bucket.file_upload.arn
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "lambda_basic" {
  name       = "lambda_basic"
  roles      = [aws_iam_role.file_parser_lambda_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_policy_attachment" "file_parser_lambda_attch" {
  name       = "file_parser_lambda_attch"
  roles      = [aws_iam_role.file_parser_lambda_role.name]
  policy_arn = aws_iam_policy.file_parser_lambda_policy.arn
}


