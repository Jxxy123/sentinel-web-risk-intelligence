"""
Sentinel Web-Risk — Core Configuration.

Environment-backed application settings for local development,
automated testing, and production deployments.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ProxyType = Literal["data_center", "isp"]
ExecutionMode = Literal["real", "mock"]


class Settings(BaseSettings):
    """
    Centralized Sentinel configuration.

    Values are loaded from environment variables or a local .env file.
    Sensitive credentials must be stored as GitHub Secrets in CI/CD.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    app_env: str = Field(
        default="development",
        validation_alias="APP_ENV",
    )

    app_host: str = Field(
        default="0.0.0.0",
        validation_alias="APP_HOST",
    )

    app_port: int = Field(
        default=8000,
        validation_alias="APP_PORT",
    )

    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )

    # ------------------------------------------------------------------
    # Provider execution mode
    # ------------------------------------------------------------------

    # real = communicate with external services
    # mock = use deterministic local providers during automated tests
    execution_mode: ExecutionMode = Field(
        default="real",
        validation_alias="EXECUTION_MODE",
    )

    # ------------------------------------------------------------------
    # AI and CrewAI providers
    # ------------------------------------------------------------------

    openai_api_key: str = Field(
        default="",
        validation_alias="OPENAI_API_KEY",
    )

    openai_base_url: str = Field(
        default="https://api.aimlapi.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )

    openai_model: str = Field(
        default="gpt-4o",
        validation_alias="OPENAI_MODEL",
    )

    # Model currently used by the CrewAI orchestration layer.
    free_tier_model: str = Field(
        default="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        validation_alias="FREE_TIER_MODEL",
    )

    anthropic_api_key: str = Field(
        default="",
        validation_alias="ANTHROPIC_API_KEY",
    )

    # ------------------------------------------------------------------
    # Bright Data shared API configuration
    # ------------------------------------------------------------------

    # Shared API key used by SERP and Web Unlocker direct API requests.
    bright_data_api_key: str = Field(
        default="",
        validation_alias="BRIGHT_DATA_API_KEY",
    )

    bright_data_request_url: str = Field(
        default="https://api.brightdata.com/request",
        validation_alias="BRIGHT_DATA_REQUEST_URL",
    )

    # ------------------------------------------------------------------
    # Bright Data SERP API
    # ------------------------------------------------------------------

    bright_data_serp_zone: str = Field(
        default="serp_api1",
        validation_alias="BRIGHT_DATA_SERP_ZONE",
    )

    bright_data_serp_api_url: str = Field(
        default="https://api.brightdata.com/request",
        validation_alias="BRIGHT_DATA_SERP_API_URL",
    )

    # ------------------------------------------------------------------
    # Bright Data Web Unlocker
    # ------------------------------------------------------------------

    bright_data_web_unlocker_zone: str = Field(
        default="web_unlocker1",
        validation_alias="BRIGHT_DATA_WEB_UNLOCKER_ZONE",
    )

    bright_data_web_unlocker_url: str = Field(
        default="https://api.brightdata.com/request",
        validation_alias="BRIGHT_DATA_WEB_UNLOCKER_URL",
    )

    # ------------------------------------------------------------------
    # Bright Data Proxy Network
    # ------------------------------------------------------------------

    bright_data_proxy_host: str = Field(
        default="brd.superproxy.io",
        validation_alias="BRIGHT_DATA_PROXY_HOST",
    )

    bright_data_proxy_port: int = Field(
        default=33335,
        validation_alias="BRIGHT_DATA_PROXY_PORT",
    )

    # Existing generic proxy credentials are the verified
    # Data Center proxy credentials.
    bright_data_proxy_user: str = Field(
        default="",
        validation_alias="BRIGHT_DATA_PROXY_USER",
    )

    bright_data_proxy_pass: str = Field(
        default="",
        validation_alias="BRIGHT_DATA_PROXY_PASS",
    )

    # Separate ISP proxy credentials.
    bright_data_isp_proxy_user: str = Field(
        default="",
        validation_alias="BRIGHT_DATA_ISP_PROXY_USER",
    )

    bright_data_isp_proxy_pass: str = Field(
        default="",
        validation_alias="BRIGHT_DATA_ISP_PROXY_PASS",
    )

    # Default proxy product used by Sentinel.
    # The actual Bright Data zone is also encoded in the proxy username.
    bright_data_zone: ProxyType = Field(
        default="data_center",
        validation_alias="BRIGHT_DATA_ZONE",
    )

    # Optional complete proxy URLs retained for compatibility with older
    # deployments. New code should prefer the individual credential fields.
    data_center_proxy: str = Field(
        default="",
        validation_alias="DATA_CENTER_PROXY",
    )

    isp_proxy: str = Field(
        default="",
        validation_alias="ISP_PROXY",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    database_url: str = Field(
        default="sqlite:///./sentinel.db",
        validation_alias="DATABASE_URL",
    )

    chroma_persist_dir: str = Field(
        default="./chroma_db",
        validation_alias="CHROMA_PERSIST_DIR",
    )

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    secret_key: str = Field(
        default="changeme",
        validation_alias="SECRET_KEY",
    )

    # ------------------------------------------------------------------
    # Normalized helper properties
    # ------------------------------------------------------------------

    @property
    def cors_origins_list(self) -> list[str]:
        """Return normalized CORS origins without empty entries."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def use_mock_providers(self) -> bool:
        """Return True when external providers must use local mocks."""
        return self.execution_mode == "mock"

    @property
    def is_production(self) -> bool:
        """Return True when Sentinel is running in production mode."""
        return self.app_env.lower() == "production"

    @property
    def proxy_endpoint(self) -> str:
        """Return the shared Bright Data proxy host and port."""
        return (
            f"{self.bright_data_proxy_host}:"
            f"{self.bright_data_proxy_port}"
        )

    def get_proxy_credentials(
        self,
        proxy_type: ProxyType | None = None,
    ) -> tuple[str, str]:
        """
        Return credentials for the selected Bright Data proxy product.

        Data Center uses the existing generic proxy secrets.
        ISP uses its dedicated ISP secrets.
        """
        selected_proxy = proxy_type or self.bright_data_zone

        if selected_proxy == "isp":
            return (
                self.bright_data_isp_proxy_user,
                self.bright_data_isp_proxy_pass,
            )

        return (
            self.bright_data_proxy_user,
            self.bright_data_proxy_pass,
        )

    def has_proxy_credentials(
        self,
        proxy_type: ProxyType | None = None,
    ) -> bool:
        """Return True when the selected proxy has both credentials."""
        username, password = self.get_proxy_credentials(proxy_type)
        return bool(username and password)


settings = Settings()
