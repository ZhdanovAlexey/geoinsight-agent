from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # vLLM
    llm_base_url: str = "http://109.230.162.92:44334/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "gpt-oss-120b"
    llm_reasoning_effort: str = "medium"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8080
    log_level: str = "INFO"
    log_format: str = "json"

    # Postgres
    postgres_dsn: str = "postgresql+psycopg://geoinsight:geoinsight@localhost:5433/geoinsight"

    # Langfuse
    langfuse_host: str = "http://localhost:3030"
    langfuse_public_url: str = ""  # browser-facing URL; falls back to langfuse_host
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_enabled: bool = True

    # Streamlit
    backend_url: str = "http://localhost:8080"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
