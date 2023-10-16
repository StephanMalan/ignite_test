################################################################################
# S3 Bucket where Iot device csv files get uploaded to
################################################################################

resource "aws_s3_bucket" "file_upload_bucket" {
  bucket        = "acme-iot-file-upload-bucket"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "file_upload_bucket_block" {
  bucket                  = aws_s3_bucket.file_upload_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_lambda_permission" "file_upload_bucket_lambda_permission" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.file_parser_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.file_upload_bucket.arn
}

resource "aws_s3_bucket_notification" "file_upload_bucket_notification" {
  bucket = aws_s3_bucket.file_upload_bucket.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.file_parser_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".txt"
  }
}


