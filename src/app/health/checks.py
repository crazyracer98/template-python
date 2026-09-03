"""Concrete health checks for this app's external services: Postgres, Redis, S3, OIDC."""

import asyncio

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from mypy_boto3_s3 import S3Client
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.health.base import HealthCheckResult


class DatabaseHealthCheck:
    """Checks that Postgres answers a trivial query through the app's async engine."""

    name = "database"

    def __init__(self, engine: AsyncEngine) -> None:
        """Bind this check to the app's shared async engine."""
        self._engine = engine

    async def check(self) -> HealthCheckResult:
        """Run `SELECT 1` and report whether it succeeded."""
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            return HealthCheckResult(self.name, healthy=False, detail=str(exc))
        return HealthCheckResult(self.name, healthy=True)


class RedisHealthCheck:
    """Checks that Redis answers PING."""

    name = "redis"

    def __init__(self, redis_url: str) -> None:
        """Bind this check to the Redis connection URL."""
        self._redis_url = redis_url

    async def check(self) -> HealthCheckResult:
        """PING Redis and report whether it succeeded."""
        client = Redis.from_url(self._redis_url)
        try:
            await client.ping()
        except RedisError as exc:
            return HealthCheckResult(self.name, healthy=False, detail=str(exc))
        finally:
            await client.aclose()
        return HealthCheckResult(self.name, healthy=True)


class S3HealthCheck:
    """Checks that the S3-compatible endpoint answers a ListBuckets call."""

    name = "s3"

    def __init__(self, endpoint_url: str, access_key: str, secret_key: str) -> None:
        """Bind this check to the S3 endpoint and credentials to connect with."""
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key

    def _list_buckets(self) -> None:
        client: S3Client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )
        client.list_buckets()

    async def check(self) -> HealthCheckResult:
        """Call ListBuckets in a thread and report whether it succeeded."""
        try:
            await asyncio.to_thread(self._list_buckets)
        except (BotoCoreError, ClientError) as exc:
            return HealthCheckResult(self.name, healthy=False, detail=str(exc))
        return HealthCheckResult(self.name, healthy=True)


class OIDCHealthCheck:
    """Checks that the OIDC provider's discovery document is reachable."""

    name = "oidc"

    def __init__(self, issuer_url: str) -> None:
        """Bind this check to the provider's issuer URL."""
        self._issuer_url = issuer_url

    async def check(self) -> HealthCheckResult:
        """Fetch the discovery document and report whether it succeeded."""
        discovery_url = f"{self._issuer_url.rstrip('/')}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return HealthCheckResult(self.name, healthy=False, detail=str(exc))
        return HealthCheckResult(self.name, healthy=True)
