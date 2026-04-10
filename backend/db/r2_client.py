from __future__ import annotations

import mimetypes

import boto3
from botocore.client import BaseClient

from backend.config import get_settings


class R2Client:
    def __init__(self) -> None:
        self._client: BaseClient | None = None

    @property
    def enabled(self) -> bool:
        settings = get_settings()
        return bool(
            settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key and settings.r2_bucket_name
        )

    def _get_client(self) -> BaseClient:
        if self._client is None:
            settings = get_settings()
            self._client = boto3.client(
                "s3",
                endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",
            )
        return self._client

    def upload_bytes(self, key: str, payload: bytes, *, content_type: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("R2 is not configured")
        guessed = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self._get_client().put_object(
            Bucket=get_settings().r2_bucket_name,
            Key=key,
            Body=payload,
            ContentType=guessed,
        )
        return key

    def public_url_for(self, key: str) -> str:
        return f"{get_settings().r2_public_url.rstrip('/')}/{key.lstrip('/')}"


r2_client = R2Client()
