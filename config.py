"""Application configuration using pydantic-settings."""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    # Database — SQLite for local dev, PostgreSQL for production
    database_url: str = f"sqlite:///{os.path.dirname(os.path.abspath(__file__))}/chatio.db"
    
    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # API Keys (third-party services)
    line_channel_id: str = ""
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_page_access_token: str = ""
    instagram_business_account_id: str = ""
    instagram_access_token: str = ""
    twitter_client_id: str = ""
    twitter_client_secret: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # AI Configuration
    ai_provider: str = "openai"  # "openai" or "anthropic"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ai_model: str = "gpt-3.5-turbo"  # gpt-3.5-turbo, gpt-4, claude-3-sonnet, etc.

    # SMTP (Gmail)
    smtp_user: str = "chatioinfo@gmail.com"
    smtp_pass: str = ""  # Gmail App Password

    # App
    app_name: str = "Chatio"
    debug: bool = True
    environment: str = "development"

    # CORS
    cors_origins: list = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]

    # URLs
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
