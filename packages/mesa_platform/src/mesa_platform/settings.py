from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MESA_", extra="ignore")

    database_url: SecretStr
    database_connect_timeout: int = Field(default=2, ge=1, le=10)
    log_level: str = "INFO"
