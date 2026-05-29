"""
Sentinel Web-Risk — Core Configuration
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # App
    app_env: str = Field(default="development", env="APP_ENV")
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    cors_origins: str = Field(default="http://localhost:3000", env="CORS_ORIGINS")

    # AI
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    openai_model: str = "gpt-4o"

    # Bright Data
    bright_data_api_key: str = Field(default="", env="BRIGHT_DATA_API_KEY")
    bright_data_serp_api_url: str = Field(
        default="https://api.brightdata.com/serp", env="BRIGHT_DATA_SERP_API_URL"
    )
    bright_data_web_unlocker_url: str = Field(
        default="https://api.brightdata.com/request", env="BRIGHT_DATA_WEB_UNLOCKER_URL"
    )
    bright_data_proxy_host: str = Field(default="brd.superproxy.io", env="BRIGHT_DATA_PROXY_HOST")
    bright_data_proxy_port: int = Field(default=33335, env="BRIGHT_DATA_PROXY_PORT") # 🔄 Updated port default matching your network settings
    bright_data_proxy_user: str = Field(default="", env="BRIGHT_DATA_PROXY_USER")
    bright_data_proxy_pass: str = Field(default="", env="BRIGHT_DATA_PROXY_PASS")
    bright_data_zone: str = Field(default="datacenter", env="BRIGHT_DATA_ZONE")

    # 🌐 New Dynamic Dual-Proxy Configuration Mappings
    data_center_proxy: str = Field(default="", env="DATA_CENTER_PROXY")
    isp_proxy: str = Field(default="", env="ISP_PROXY")

    # Database
    database_url: str = Field(default="sqlite:///./sentinel.db", env="DATABASE_URL")
    chroma_persist_dir: str = Field(default="./chroma_db", env="CHROMA_PERSIST_DIR")

    # Security
    secret_key: str = Field(default="changeme", env="SECRET_KEY")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 🛡️ Added to safely allow Groq / extra provider vars in your .env file


settings = Settings()