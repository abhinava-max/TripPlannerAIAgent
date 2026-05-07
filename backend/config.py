from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    RAPIDAPI_KEY: str
    AERODATABOX_HOST: str = "aerodatabox.p.rapidapi.com"

    WEATHER_API_KEY: str

    EXCHANGE_RATE_API_KEY: str

    GEOAPIFY_API_KEY: str

    HF_TOKEN: str
    HF_EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"

    CHROMA_DB_PATH: str = "./chroma_db"
    POLICY_DOCS_PATH: str = "policy_docs"
    POLICY_COLLECTION_NAME: str = "travel_policy_docs"

    AGENT_TOOL_DELAY_SECONDS: float = 2.0
    AGENT_TOOL_RETRIES: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
