import boto3

from app.config import get_settings

settings = get_settings()

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
    return _s3_client


def upload_file(local_path: str, key: str) -> str:
    client = get_s3_client()
    client.upload_file(local_path, settings.s3_bucket, key)
    return key


def signed_url(key: str | None, expires_in: int = 3600) -> str | None:
    if not key:
        return None
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
