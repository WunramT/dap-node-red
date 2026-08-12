"""
Authentication endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_user_roles
from app.core.auth_factory import get_auth_provider
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token
)
from app.models.person import Person
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    AzureLoginRequest,
    MasterPasswordLoginRequest,
    PasswordOnlyLoginRequest,
    AuthModeResponse,
    AuthConfigResponse,
    UserInfo,
    MessageResponse
)
from app.config import settings


router = APIRouter()


@router.get("/config", response_model=AuthConfigResponse, status_code=status.HTTP_200_OK)
async def get_auth_config():
    """
    Get the full authentication configuration.

    Returns active providers, passwordless flag and the current mode so that
    the frontend can render the correct login UI and route guards.
    In development mode the list of available roles is included.
    """
    available_roles = None
    if settings.is_development:
        # Expose at least the two baseline roles; projects can extend this list.
        available_roles = ["admin", "user"]

    return AuthConfigResponse(
        mode=settings.mode,
        providers={
            "azure": settings.auth_provider_azure,
            "local_db": settings.auth_provider_local_db,
            "master_pw": settings.auth_provider_master_pw,
        },
        passwordless=settings.user_passwordless,
        available_roles=available_roles,
    )


@router.get("/mode", response_model=AuthModeResponse, status_code=status.HTTP_200_OK)
async def get_auth_mode():
    """
    Get the current application mode.

    Kept for backward compatibility. Prefer /config for new code.
    """
    return AuthModeResponse(mode=settings.mode)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password (AUTH_PROVIDER_LOCAL_DB).

    Returns access and refresh tokens.
    """
    provider = get_auth_provider(db, "local_db")
    person = await provider.authenticate(credentials.model_dump())

    if not person or not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    person.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    roles = await provider.get_user_roles(person)
    primary_role = roles[0] if roles else "user"

    access_token = create_access_token({
        "sub": str(person.id),
        "role": primary_role,
        "provider": "local_db",
    })
    refresh_token = create_refresh_token({"sub": str(person.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/azure-login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def azure_login(
    credentials: AzureLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with Azure AD token (AUTH_PROVIDER_AZURE – token exchange).

    Validates the Azure AD access token, creates/updates the user in the
    database, syncs roles, and returns backend JWT tokens.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Azure login request received")

    provider = get_auth_provider(db, "azure")
    person = await provider.authenticate({"token": credentials.token})

    if not person or not person.is_active:
        logger.error("Azure authentication failed - person not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Azure authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Azure authentication successful for person: {person.email}")

    person.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    roles = await provider.get_user_roles(person)
    primary_role = roles[0] if roles else "user"

    access_token = create_access_token({
        "sub": str(person.id),
        "role": primary_role,
        "provider": "azure",
    })
    refresh_token = create_refresh_token({"sub": str(person.id)})

    logger.info("Backend JWT tokens created successfully")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/master-pw-login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def master_pw_login(
    credentials: MasterPasswordLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with master password (AUTH_PROVIDER_MASTER_PW).

    - Correct MASTER_PASSWORD_ADMIN → role "admin"
    - Correct MASTER_PASSWORD_USER  → role "user"  (if configured)
    - Wrong password → 401
    """
    provider = get_auth_provider(db, "master_pw")
    person = await provider.authenticate({"password": credentials.password})

    if not person or not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect master password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    person.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    roles = await provider.get_user_roles(person)
    primary_role = roles[0] if roles else "user"

    access_token = create_access_token({
        "sub": str(person.id),
        "role": primary_role,
        "provider": "master_pw",
    })
    refresh_token = create_refresh_token({"sub": str(person.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/passwordless-token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def passwordless_token(
    db: AsyncSession = Depends(get_db)
):
    """
    Obtain a token with role "user" without any credentials (USER_PASSWORDLESS).

    This endpoint is called automatically on app start when USER_PASSWORDLESS=T
    so every visitor can access user-level functionality without logging in.
    """
    provider = get_auth_provider(db, "passwordless")
    person = await provider.authenticate({})

    if not person or not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Passwordless user not found. Ensure seed users have been initialized.",
        )

    access_token = create_access_token({
        "sub": str(person.id),
        "role": "user",
        "provider": "passwordless",
    })
    refresh_token = create_refresh_token({"sub": str(person.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


# ---------------------------------------------------------------------------
# Backward-compat endpoint – maps old password_only schema to master_pw
# ---------------------------------------------------------------------------
@router.post("/password-login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def password_only_login(
    credentials: PasswordOnlyLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Backward-compatible password-only login endpoint.

    Delegates to /master-pw-login (admin) or /passwordless-token (user).
    Prefer the dedicated endpoints in new code.
    """
    if credentials.role == "admin":
        if not credentials.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required for admin role",
            )
        return await master_pw_login(
            MasterPasswordLoginRequest(password=credentials.password), db
        )
    # role == "user" → passwordless
    return await passwordless_token(db)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Returns new access and refresh tokens.
    """
    payload = decode_refresh_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    person_id = payload.get("sub")
    if not person_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    person = await db.get(Person, person_id)
    if not person or not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Preserve original provider claim if present
    provider = payload.get("provider", "unknown")
    role = payload.get("role", "user")

    access_token = create_access_token({
        "sub": str(person.id),
        "role": role,
        "provider": provider,
    })
    new_refresh_token = create_refresh_token({"sub": str(person.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.post("/logout", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def logout(
    current_user: Person = Depends(get_current_user)
):
    """
    Logout current user.

    Since JWTs are stateless, logout is handled client-side by removing the
    tokens from storage. This endpoint exists for potential future token
    blacklisting and for consistency.
    """
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
async def get_current_user_info(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user's information.

    Returns user details including roles.
    """
    roles = await get_current_user_roles(current_user, db)

    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        roles=roles,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at
    )

