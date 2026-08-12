"""
Health check endpoint tests.

These are simple smoke tests to verify the API is working correctly.
"""
import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestHealthEndpoint:
    """Test the health check endpoint."""

    async def test_health_check_returns_200(self, async_client: AsyncClient):
        """Test that health endpoint returns 200 OK."""
        response = await async_client.get("/api/health")

        assert response.status_code == 200

    async def test_health_check_response_structure(self, async_client: AsyncClient):
        """Test that health endpoint returns expected structure."""
        response = await async_client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "database" in data
        assert "environment" in data
        assert "version" in data

    async def test_health_check_status_healthy(self, async_client: AsyncClient):
        """Test that health endpoint reports healthy status."""
        response = await async_client.get("/api/health")
        data = response.json()

        assert data["status"] == "healthy"


class TestRootEndpoint:
    """Test the root endpoint."""

    async def test_root_returns_200(self, async_client: AsyncClient):
        """Test that root endpoint returns 200 OK."""
        response = await async_client.get("/api/")

        assert response.status_code == 200

    async def test_root_response_structure(self, async_client: AsyncClient):
        """Test that root endpoint returns expected structure."""
        response = await async_client.get("/api/")
        data = response.json()

        assert "message" in data
        assert "version" in data
        assert "docs" in data


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    async def test_openapi_json_available(self, async_client: AsyncClient):
        """Test that OpenAPI JSON is available."""
        response = await async_client.get("/api/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    async def test_swagger_ui_available(self, async_client: AsyncClient):
        """Test that Swagger UI is available."""
        response = await async_client.get("/api/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_redoc_available(self, async_client: AsyncClient):
        """Test that ReDoc is available."""
        response = await async_client.get("/api/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
