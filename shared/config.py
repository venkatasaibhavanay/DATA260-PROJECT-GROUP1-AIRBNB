"""Infrastructure settings shared by every service.

Settings are read from environment variables first, then from the repository-root
.env file. Defaults target services running on the host against the Docker
infrastructure (host ports). Inside the Docker network override with:
    MYSQL_HOST=mysql MYSQL_PORT=3306 MONGO_HOST=mongodb MONGO_PORT=27017
    REDIS_HOST=redis REDIS_PORT=6379 KAFKA_BOOTSTRAP_SERVERS=kafka:29092
"""
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


class InfraSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = "development"
    cors_origins: str = "http://localhost:5101,http://127.0.0.1:5101"

    mysql_host: str = "localhost"
    mysql_port: int = 3311
    mysql_database: str = "airbnb_group1"
    mysql_user: str = "group1_app"
    mysql_password: str = ""

    mongo_host: str = "localhost"
    mongo_port: int = 27101
    mongo_database: str = "airbnb_group1"
    mongo_root_user: str = "group1_admin"
    mongo_root_password: str = ""

    redis_host: str = "localhost"
    redis_port: int = 6381
    redis_password: str = ""

    kafka_bootstrap_servers: str = "localhost:9091"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.mysql_user)}:{quote_plus(self.mysql_password)}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def mongo_uri(self) -> str:
        return (
            f"mongodb://{quote_plus(self.mongo_root_user)}:{quote_plus(self.mongo_root_password)}"
            f"@{self.mongo_host}:{self.mongo_port}/?authSource=admin"
        )
