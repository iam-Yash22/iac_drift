terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "iac_driftwatch_role" {
  name = var.role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DriftWatchAssumeRole"
      Effect = "Allow"
      Principal = {
        AWS = var.driftwatch_principal_arn
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "sts:ExternalId" = var.external_id
        }
      }
    }]
  })

  tags = {
    ManagedBy   = "Terraform"
    Application = "IaC DriftWatch"
  }

  lifecycle {
    prevent_destroy = true
  }
}

 resource "aws_iam_role_policy_attachment" "read_only" {
    role       = aws_iam_role.iac_driftwatch_role.name
    policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

output "role_arn" {
  value = "arn:aws:iam::740122274365:user/iac"
}

output "target_account_id" {
  value = "740122274365"
}
