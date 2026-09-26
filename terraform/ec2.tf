# ec2_test.tf
# Place in the SAME terraform directory as your S3/SG/Lambda baseline —
# same state file rule as before.

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "ec2_test_sg" {
  name        = "driftwatch-test-ec2-sg"
  description = "Test SG for DriftWatch EC2 drift test"

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Application = "IaC DriftWatch"
    ManagedBy   = "Terraform"
    Name        = "driftwatch-test-ec2-sg"
  }
}

resource "aws_instance" "test_instance" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.micro" # classic free-tier eligible
  vpc_security_group_ids = [aws_security_group.ec2_test_sg.id]

  tags = {
    Application = "IaC DriftWatch"
    ManagedBy   = "Terraform"
    Name        = "driftwatch-test-ec2"
  }
}

output "test_instance_id" {
  value = aws_instance.test_instance.id
}