import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_or_create_cookie_secret() -> str:
    secret = os.getenv("COOKIE_SECRET")
    if secret:
        return secret
    secret_file = Path(".cookie_secret")
    if secret_file.exists():
        return secret_file.read_text().strip()
    import secrets
    secret = secrets.token_hex(32)
    secret_file.write_text(secret)
    secret_file.chmod(0o600)
    return secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/ordering_db"

    # Security
    COOKIE_SECRET: str = ""
    ENV: str = ""

    # AI
    AGY_HOST_URL: str = ""

    # Testing
    TESTING: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.TESTING == "1"

    def model_post_init(self, __context):
        if not self.COOKIE_SECRET:
            self.COOKIE_SECRET = _load_or_create_cookie_secret()


settings = Settings()
