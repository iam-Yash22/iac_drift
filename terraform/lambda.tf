# lambda_test.tf
# Place this file in the SAME terraform directory as your existing
# S3/SG baseline (not terraform_samples/ or any separate dir) — it must
# land in the same state file your app's baseline loader already reads,
# or the app won't see it as part of the baseline at all.


resource "aws_iam_role" "lambda_exec" {
  name = "driftwatch-test-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = {
    Application = "IaC DriftWatch"
    ManagedBy   = "Terraform"
    Name        = "driftwatch-test-lambda-exec"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_test_payload.zip"

  source {
    filename = "index.py"
    content  = <<-EOF
      def handler(event, context):
          return {"statusCode": 200, "body": "driftwatch test function"}
    EOF
  }
}

resource "aws_lambda_function" "test_fn" {
  function_name    = "driftwatch-test-fn"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 10
  memory_size      = 128

  tags = {
    Application = "IaC DriftWatch"
    ManagedBy   = "Terraform"
    Name        = "driftwatch-test-fn"
  }
}

output "test_lambda_arn" {
  value = aws_lambda_function.test_fn.arn
}

output "test_lambda_role_arn" {
  value = aws_iam_role.lambda_exec.arn
}