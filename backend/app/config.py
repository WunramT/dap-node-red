"""
Application configuration using Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List


class Settings(BaseSettings):
    """
    Application settings with type safety and validation.

    All settings can be overridden via environment variables.
    """

    # Application
    app_name: str = "dapnodered API"
    app_version: str = "1.0.0"
    debug: bool = False
    root_path: str = ""
    enable_auth: bool = True
    # Sentry Configuration
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 1.0
    sentry_profiles_sample_rate: float = 1.0

    # Security
    secret_key: str  # Required - must be set via environment variable

    # Application mode Default production to be sure, that auth providers are not bypassed by default
    # "development" → auth providers are bypassed; role switcher + seed users are active
    # "production"  → at least one provider or USER_PASSWORDLESS must be enabled
    mode: str = "production"

    # Authentication providers (T/F or true/false)
    auth_provider_azure: bool = False      # Azure AD / Entra ID SSO
    auth_provider_local_db: bool = False   # E-mail + password against local DB
    auth_provider_master_pw: bool = False  # Single master-password login

    # Passwordless access – grants role "user" without any login
    user_passwordless: bool = False

    # Master-password credentials (required when auth_provider_master_pw=True)
    master_password_admin: str = ""   # Password granting "admin" role
    master_password_user: str = ""    # Optional password granting "user" role

    # Default role shown in dev-mode role switcher
    dev_user_role: str = "user"

    @field_validator(
        'auth_provider_azure', 'auth_provider_local_db',
        'auth_provider_master_pw', 'user_passwordless',
        mode='before'
    )
    @classmethod
    def parse_bool_flag(cls, v) -> bool:
        """Accept T/F in addition to Pydantic's standard true/false/1/0."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.upper() in ('T', 'TRUE', '1', 'YES', 'ON')
        return bool(v)

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate that MODE is a valid value."""
        valid_modes = ('development', 'production')
        if v not in valid_modes:
            raise ValueError(f'MODE must be one of: {valid_modes}')
        return v

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate that SECRET_KEY is secure."""
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters')
        insecure_keys = (
            'dev-secret-key-change-in-production',
            'changeme',
            'secret',
            'password',
        )
        if v.lower() in insecure_keys:
            raise ValueError('Default/insecure SECRET_KEY must not be used')
        return v

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Azure Entra ID Configuration
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Database
    database_host: str = "postgres"
    database_port: int = 5432
    database_name: str = "app_db"
    database_schema: str = "public"
    database_user: str = "dev_user"
    database_password: str = "dev_password"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Application Limits
    max_content_length: int = 16 * 1024 * 1024  # 16MB

    # Allowed document types for upload
    allowed_document_types: list = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "message/rfc822",  # .eml files
        "application/vnd.ms-outlook",  # .msg files
        "application/octet-stream",  # Fallback for .msg files (browser doesn't recognize the type)
    ]
    allowed_document_extensions: list = [".pdf", ".jpg", ".jpeg", ".png", ".eml", ".msg"]

    # Scheduler Configuration
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Berlin"
    scheduler_system_user_email: str = "admin@{{PROJECT_DOMAIN}}"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @model_validator(mode='after')
    def validate_production_settings(self):
        """Validate that production mode has at least one auth method configured."""
        if self.mode == 'production':
            has_provider = any([
                self.auth_provider_azure,
                self.auth_provider_local_db,
                self.auth_provider_master_pw,
                self.user_passwordless,
            ])
            if not has_provider:
                raise ValueError(
                    'MODE=production requires at least one AUTH_PROVIDER_* or USER_PASSWORDLESS to be enabled.'
                )
            if self.auth_provider_master_pw and not self.master_password_admin:
                raise ValueError(
                    'MASTER_PASSWORD_ADMIN must be set when AUTH_PROVIDER_MASTER_PW is enabled.'
                )
        return self

    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.mode == "development"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def database_url(self) -> str:
        """
        Async PostgreSQL connection URL for SQLAlchemy.
        Uses asyncpg driver for async operations.
        """
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def sync_database_url(self) -> str:
        """
        Sync PostgreSQL connection URL for Alembic migrations.
        Alembic requires synchronous database connections.
        """
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


# Global settings instance
settings = Settings()
