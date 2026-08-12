"""
Azure Entra ID authentication provider.
Validates Azure AD JWT tokens and extracts user/role information.
"""
from typing import Dict, Any, List, Optional
import jwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_provider import AuthProvider
from app.config import settings


class EntraAuthProvider(AuthProvider):
    """
    Azure Entra ID authentication provider.

    Validates JWT tokens issued by Azure AD and extracts user claims
    including roles from the token.
    """

    # Azure AD role to local role mapping
    ROLE_MAPPING = {
        "Admin": "admin",
        "User": "user",
    }

    def __init__(self, db: AsyncSession):
        """
        Initialize Entra ID auth provider.

        Args:
            db: AsyncSession for database operations
        """
        super().__init__(db)
        self._jwks_client: Optional[PyJWKClient] = None

    @property
    def jwks_uri(self) -> str:
        """Get the JWKS URI for Azure AD."""
        return f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys"

    @property
    def issuer(self) -> str:
        """Get the expected token issuer."""
        return f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0"

    @property
    def audience(self) -> str:
        """Get the expected token audience (client ID)."""
        return settings.azure_client_id

    def _get_jwks_client(self) -> PyJWKClient:
        """Get or create JWKS client for key retrieval."""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_uri)
        return self._jwks_client

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate Azure AD JWT token.
        Accepts tokens from both Azure AD v1.0 and v2.0 endpoints.

        Args:
            token: JWT token from Authorization header

        Returns:
            Decoded token claims if valid, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Get the signing key from Azure AD
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            logger.info("Successfully retrieved signing key from JWKS")

            # First decode without full validation to check issuer
            unverified_claims = jwt.decode(
                token,
                options={
                    # nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False
                }
            )

            token_issuer = unverified_claims.get("iss", "")

            # Accept both v1.0 and v2.0 issuers
            v1_issuer = f"https://sts.windows.net/{settings.azure_tenant_id}/"
            v2_issuer = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0"

            if token_issuer not in [v1_issuer, v2_issuer]:
                logger.error(f"Invalid issuer: {token_issuer}. Expected {v1_issuer} or {v2_issuer}")
                return None

            logger.info(f"Token issuer validated: {token_issuer}")

            # Check audience manually (accept both formats)
            token_audience = unverified_claims.get("aud", "")
            expected_audiences = [
                settings.azure_client_id,  # Just the client ID
                f"api://{settings.azure_client_id}"  # With api:// prefix
            ]

            if token_audience not in expected_audiences:
                logger.error(f"Invalid audience: {token_audience}. Expected one of {expected_audiences}")
                return None

            logger.info(f"Token audience validated: {token_audience}")

            # Now decode and validate with signature check (skip issuer and audience since validated above)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={
                    "verify_exp": True,
                    "verify_aud": False,  # Validated manually above
                    "verify_iss": False,  # Validated manually above
                }
            )

            logger.info("Token validation successful")
            return claims

        except jwt.ExpiredSignatureError as e:
            logger.error(f"Token validation failed - EXPIRED SIGNATURE: {str(e)}")
            return None
        except jwt.InvalidAudienceError as e:
            logger.error(f"Token validation failed - INVALID AUDIENCE: {str(e)}")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Token validation failed - INVALID TOKEN: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Token validation failed - UNEXPECTED ERROR: {type(e).__name__}: {str(e)}", exc_info=True)
            return None

    def _extract_roles_from_claims(self, claims: Dict[str, Any]) -> List[str]:
        """
        Extract roles from token claims.

        Azure AD stores roles in the 'roles' claim.

        Args:
            claims: Decoded token claims

        Returns:
            List of local role names
        """
        azure_roles = claims.get("roles", [])
        local_roles = []

        for azure_role in azure_roles:
            if azure_role in self.ROLE_MAPPING:
                local_roles.append(self.ROLE_MAPPING[azure_role])

        # Default to 'user' if no roles found
        if not local_roles:
            local_roles.append("user")

        return local_roles

    async def authenticate(self, credentials: Dict[str, Any]):
        """
        Authenticate user with Azure AD token.

        Args:
            credentials: Dict with 'token' key containing the JWT

        Returns:
            Person object if authentication successful, None otherwise
        """
        from app.models.person import Person
        from app.models.role import Role
        from app.models.person_role import PersonRole

        token = credentials.get("token")
        if not token:
            return None

        # Validate the token
        claims = await self.validate_token(token)
        if not claims:
            return None

        # Extract user info from claims
        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        oid = claims.get("oid")  # Azure AD Object ID

        if not email:
            return None

        # Use given_name and family_name if available, fallback to parsing name
        first_name = claims.get("given_name", "")
        last_name = claims.get("family_name", "")

        # Fallback: parse from name if given_name/family_name not available
        if not first_name or not last_name:
            name = claims.get("name", "")
            if name:
                name_parts = name.split(" ", 1)
                first_name = first_name or name_parts[0]
                last_name = last_name or (name_parts[1] if len(name_parts) > 1 else "")

        # Check if user exists
        stmt = (
            select(Person)
            .where(Person.email == email)
            .where(Person.deleted_at.is_(None))
            .options(selectinload(Person.roles))
        )
        result = await self.db.execute(stmt)
        person = result.scalar_one_or_none()

        # Extract roles from token
        token_roles = self._extract_roles_from_claims(claims)

        if person:
            # Update existing user's info
            person.first_name = first_name
            person.last_name = last_name
            person.entra_object_id = oid
            person.auth_source = "entra_id"
            person.is_active = True

            # Sync roles from token
            await self._sync_roles(person, token_roles)

        else:
            # Create new user
            person = Person(
                email=email,
                first_name=first_name,
                last_name=last_name,
                entra_object_id=oid,
                auth_source="entra_id",
                is_active=True,
            )
            self.db.add(person)
            await self.db.flush()

            # Assign roles from token
            await self._sync_roles(person, token_roles)

        await self.db.commit()
        return person

    async def _sync_roles(self, person, role_names: List[str]) -> None:
        """
        Sync person's roles with the roles from the token.

        Args:
            person: Person object
            role_names: List of role names from token
        """
        from app.models.role import Role
        from app.models.person_role import PersonRole

        # Get all existing roles
        role_stmt = select(Role).where(Role.name.in_(role_names))
        result = await self.db.execute(role_stmt)
        roles = result.scalars().all()

        # Get existing person roles
        existing_stmt = select(PersonRole).where(PersonRole.person_id == person.id)
        existing_result = await self.db.execute(existing_stmt)
        existing_person_roles = existing_result.scalars().all()

        existing_role_ids = {pr.role_id for pr in existing_person_roles}
        new_role_ids = {r.id for r in roles}

        # Remove roles that are no longer in the token
        for pr in existing_person_roles:
            if pr.role_id not in new_role_ids:
                await self.db.delete(pr)

        # Add new roles from token
        for role in roles:
            if role.id not in existing_role_ids:
                person_role = PersonRole(person_id=person.id, role_id=role.id)
                self.db.add(person_role)

    async def get_user_roles(self, person) -> List[str]:
        """
        Get roles for authenticated person.

        Args:
            person: Person object

        Returns:
            List of role names
        """
        from app.models.person_role import PersonRole
        from app.models.role import Role

        stmt = (
            select(Role)
            .join(PersonRole)
            .where(PersonRole.person_id == person.id)
        )

        result = await self.db.execute(stmt)
        roles = result.scalars().all()

        return [role.name for role in roles]

    async def supports_registration(self) -> bool:
        """
        Entra ID does not support local registration.

        Returns:
            False (registration handled by Azure AD)
        """
        return False
