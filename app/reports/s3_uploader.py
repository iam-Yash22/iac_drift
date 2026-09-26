import boto3

from app.core.config import settings


class S3Uploader:
    """Upload generated report content to the configured reports S3 bucket."""

    def __init__(self, bucket_name: str | None = None):
        self.bucket_name = bucket_name or settings.REPORTS_BUCKET_NAME
        self.client = boto3.client("s3")

    def upload(self, key: str, content: bytes) -> str:
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content,
        )

        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=900,
        )
