# config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    database_host: str = os.environ["DATABASE_HOST"]
    database_name: str = os.environ["DATABASE_NAME"]
    database_user: str = os.environ["DATABASE_USER"]
    database_password: str = os.environ["DATABASE_PASSWORD"]
    database_port: int = int(os.environ["DATABASE_PORT"])

    telegram_bot_url: str = os.environ["TELEGRAM_BOT_URL"]
    telegram_chat_id: str = os.environ["TELEGRAM_CHAT_ID"]

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"


settings = Settings()