"""
API v1 router aggregation.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import health, auth, persons

# Create main API router
api_router = APIRouter()

# Include health endpoints (no prefix)
api_router.include_router(
    health.router,
    tags=["health"]
)

# Include auth endpoints
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

# Include person management endpoints
api_router.include_router(
    persons.router,
    prefix="/persons",
    tags=["persons"]
)

# Add your custom routes here:
# api_router.include_router(
#     your_router.router,
#     prefix="/your-resource",
#     tags=["your-resource"]
# )
