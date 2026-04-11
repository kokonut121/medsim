from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MedSim"
    app_env: str = Field(default="development", alias="MEDSENTINEL_ENV")
    iris_mode: Literal["memory", "fhir", "native"] = Field(default="memory", alias="MEDSENTINEL_IRIS_MODE")

    iris_host: str = "localhost"
    iris_port: int = 1972
    iris_namespace: str = "MEDSENT"
    iris_user: str = "medsent_app"
    iris_password: str = "changeme"
    iris_fhir_base: str = "http://localhost:52773/fhir/r4"
    iris_connect_timeout_ms: int = 10000
    iris_sharedmemory: bool = False
    iris_health_connect_endpoint: str = ""

    google_api_key: str = ""
    google_geocoding_api_key: str = ""
    world_labs_api_key: str = ""
    world_labs_api_base: str = "https://api.worldlabs.ai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    modal_token_id: str = ""
    modal_token_secret: str = ""
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "medsent-assets"
    r2_public_url: str = "https://example.r2.dev"
    fal_key: str = ""
    use_synthetic_fallbacks: bool = Field(default=False, alias="MEDSENTINEL_USE_SYNTHETIC_FALLBACKS")
    next_public_mapbox_token: str = ""
    next_public_ws_url: str = "ws://127.0.0.1:8000"
    next_public_api_url: str = "http://127.0.0.1:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
