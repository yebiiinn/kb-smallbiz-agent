from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parent
ENV_FILE = PROJECT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:3000"

    # API KEY (.env) — 호출 URL은 tools/*.py 상단 API_URL
    sangkwon_api_key: str = ""
    seoul_sales_api_key: str = ""
    kakao_rest_api_key: str = ""
    ecos_api_key: str = ""
    kosis_api_key: str = ""
    kosis_consumption_itm_id: str = ""
    kosis_consumption_obj_id: str = ""
    bizinfo_api_key: str = ""
    finlife_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
