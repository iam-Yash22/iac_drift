terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  description = "AWS region in which to create the security group."
  type        = string
  default     = "eu-north-1"
}

variable "aws_access_key" {
  description = "AWS access key for the sandbox account."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^(AKIA|ASIA)[A-Z0-9]{16}$", var.aws_access_key))
    error_message = "aws_access_key must be a 20-character AWS access key beginning with AKIA or ASIA."
  }
}

variable "aws_secret_key" {
  description = "AWS secret access key for the sandbox account."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Za-z0-9/+=]{40}$", var.aws_secret_key))
    error_message = "aws_secret_key must be a 40-character AWS secret access key."
  }
}

variable "bucket_name" {
  description = "Globally unique name for the S3 bucket."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID in which to create the security group."
  type        = string
}

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${replace(var.bucket_name, "_", "-")}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket" "driftwatch" {
  bucket = local.bucket_name

  tags = {
    Name        = local.bucket_name
    ManagedBy   = "Terraform"
    Application = "IaC DriftWatch"
  }
}

resource "aws_s3_bucket_public_access_block" "driftwatch" {
  bucket = aws_s3_bucket.driftwatch.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_security_group" "s3_access" {
  name        = "${local.bucket_name}-access"
  description = "Security group for VPC resources that access the DriftWatch S3 bucket. S3 itself does not attach to security groups."
  vpc_id      = var.vpc_id

  egress {
    description = "Allow HTTPS access to AWS services"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.bucket_name}-access"
    ManagedBy   = "Terraform"
    Application = "IaC DriftWatch"
  }
}

output "s3_bucket_name" {
  description = "Name of the created S3 bucket."
  value       = local.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the created S3 bucket."
  value       = aws_s3_bucket.driftwatch.arn
}

output "security_group_id" {
  description = "ID of the security group for VPC resources accessing the bucket."
  value       = aws_security_group.s3_access.id
}