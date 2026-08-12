"""
Health check and root endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import get_db
from app.config import settings

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint with database connectivity verification.

    Returns:
        dict: Status information including database health
    """
    try:
        await db.execute(text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'

    return {
        'status': 'healthy',
        'database': db_status,
        'environment': 'development' if settings.debug else 'production',
        'version': settings.app_version
    }


@router.get("/", tags=["root"])
async def root():
    """
    Root endpoint providing basic API information.

    Returns:
        dict: API name, version, and documentation URL
    """
    return {
        'message': settings.app_name,
        'version': settings.app_version,
        'docs': '/api/docs',
        'redoc': '/api/redoc'
    }
