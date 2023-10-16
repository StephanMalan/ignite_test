################################################################################
# API Gateway that triggers Lambda function to retrieve Iot data from RDS
################################################################################

resource "aws_apigatewayv2_api" "data_retrieval_api" {
  name          = "data_retrieval_api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "data_retrieval_api_dev_stage" {
  name        = "data_retrieval_api_dev_stage"
  api_id      = aws_apigatewayv2_api.data_retrieval_api.id
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.data_retrieval_api_log_group.arn

    format = jsonencode({
      requestId               = "$context.requestId"
      sourceIp                = "$context.identity.sourceIp"
      requestTime             = "$context.requestTime"
      protocol                = "$context.protocol"
      httpMethod              = "$context.httpMethod"
      resourcePath            = "$context.resourcePath"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_cloudwatch_log_group" "data_retrieval_api_log_group" {
  name              = "/aws/api-gw/${aws_apigatewayv2_api.data_retrieval_api.name}"
  retention_in_days = 7
}

resource "aws_apigatewayv2_integration" "data_retrieval_api_integration" {
  api_id             = aws_apigatewayv2_api.data_retrieval_api.id
  integration_uri    = aws_lambda_function.data_retrieval_lambda.invoke_arn
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "data_retrieval_api_get_data_route" {
  api_id    = aws_apigatewayv2_api.data_retrieval_api.id
  route_key = "GET /data"
  target    = "integrations/${aws_apigatewayv2_integration.data_retrieval_api_integration.id}"
}

resource "aws_lambda_permission" "data_retrieval_api_lambda_perm" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_retrieval_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.data_retrieval_api.execution_arn}/*/*"
}
