"""Security and authentication utilities."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from app.config import settings


# JWT settings
SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


# ============================================================================
# Password Hashing (bcrypt with SHA-256 Prehashing)
# ============================================================================
#
# MIGRATION WARNING:
# This implementation uses SHA-256 prehashing before bcrypt. This is NOT
# compatible with previous password hashes created using passlib's CryptContext.
#
# If migrating an existing project with stored password hashes, you MUST
# implement a re-hashing mechanism, e.g.:
#   1. On login, verify with old method first (passlib)
#   2. If successful, re-hash with new method and update DB
#   3. After all users have re-logged, remove old verification code
#
# For new projects, this is the recommended approach as it handles passwords
# longer than bcrypt's 72-byte limit safely.
# ============================================================================


def hash_password(plain_password: str) -> str:
    """
    Hash a password using bcrypt with SHA-256 prehashing.

    SHA-256 prehashing converts any password (including those > 72 bytes) into
    a fixed 44-byte Base64 string, ensuring bcrypt's 72-byte limit is never
    exceeded while maintaining full entropy.

    Note: CodeQL may flag the SHA-256 step as "weak" for passwords, but this is
    a false positive. SHA-256 is used only as a length-normalization step BEFORE
    bcrypt. The actual security comes from bcrypt's 12-round work factor.

    Args:
        plain_password: The plain text password to hash

    Returns:
        The bcrypt hash string (suitable for database storage)
    """
    # SHA-256 Prehash: Converts arbitrary-length passwords to 44 bytes Base64,
    # so bcrypt's 72-byte limit is never an issue.
    # Security note: SHA-256 here is NOT the password hash - it's a preprocessing
    # step. The actual work factor comes from bcrypt.hashpw() below.
    sha256_digest = hashlib.sha256(plain_password.encode("utf-8")).digest()  # noqa: S324
    prehashed = base64.b64encode(sha256_digest)
    return bcrypt.hashpw(prehashed, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its bcrypt hash.

    Uses the same SHA-256 prehashing as hash_password() to ensure compatibility.

    Note: CodeQL may flag the SHA-256 step as "weak" for passwords, but this is
    a false positive. See hash_password() docstring for explanation.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The stored bcrypt hash

    Returns:
        True if password matches, False otherwise
    """
    # SHA-256 prehash must match the hashing step for verification to work.
    # Security comes from bcrypt.checkpw(), not from SHA-256.
    sha256_digest = hashlib.sha256(plain_password.encode("utf-8")).digest()  # noqa: S324
    prehashed = base64.b64encode(sha256_digest)
    return bcrypt.checkpw(prehashed, hashed_password.encode("utf-8"))


# Alias for backward compatibility (deprecated, use hash_password instead)
def get_password_hash(password: str) -> str:
    """
    Hash a password.

    DEPRECATED: Use hash_password() instead. This alias exists only for
    backward compatibility and will be removed in a future version.

    Args:
        password: The plain text password to hash

    Returns:
        The bcrypt hash string
    """
    return hash_password(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary containing token data.
              May include 'role' and 'provider' claims.
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Dictionary containing token data
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def decode_refresh_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT refresh token.

    Args:
        token: JWT refresh token string

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
