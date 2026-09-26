variable "aws_region" {
  description = "AWS region used by the provider. IAM is global, but the provider still requires a region."
  type        = string
  default     = "us-east-1"
}

variable "role_name" {
  description = "Existing IAM role name in the target account."
  type        = string
  default     = "DriftWatch_ReadOnly_Role"
}

variable "driftwatch_principal_arn" {
  description = "ARN of the management-account role or user allowed to assume the read-only role."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/.+$", var.driftwatch_principal_arn))
    error_message = "Provide a valid IAM role or user ARN from the DriftWatch management account."
  }
}

variable "external_id" {
  description = "Exact external ID required by the DriftWatchReadOnlyRole trust policy."
  type        = string
  sensitive   = true

  validation {
    condition     = length(trimspace(var.external_id)) > 0 && length(var.external_id) <= 255
    error_message = "external_id must be the exact non-empty value stored for this account."
  }
}
