import os
from typing import Any, Dict, Optional

from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseSettings, EmailStr, SecretStr, validator


class Settings(BaseSettings):
    PROJECT_NAME: str

    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_URI: Optional[str] = None

    @validator("POSTGRES_URI", pre=True)
    def validate_postgres_conn(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if isinstance(v, str):
            return v
        password: SecretStr = values.get("POSTGRES_PASSWORD", SecretStr(""))
        return "{scheme}://{user}:{password}@{host}/{db}".format(
            scheme="postgresql+asyncpg",
            user=values.get("POSTGRES_USER"),
            password=password.get_secret_value(),
            host=values.get("POSTGRES_HOST"),
            db=values.get("POSTGRES_DB"),
        )

    FIRST_USER_EMAIL: EmailStr
    FIRST_USER_PASSWORD: SecretStr

    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    REDIS_HOST: str
    REDIS_PORT: int

    BOT_TOKEN: str

    def get_bot_token(self):
        self.BOT_TOKEN = os.environ.get("BOT_TOKEN")
        return self.BOT_TOKEN

    def get_telegram_url(self):
        return "https://api.telegram.org/bot{}/".format(self.BOT_TOKEN)


settings = Settings()

# create dataclass for telegram bot with token , url and sendMessage method


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.url = "https://api.telegram.org/bot{}/".format(self.token)

    def sendMessage(self, chat_id: int, text: str):
        url = self.url + "sendMessage"
        params = {"chat_id": chat_id, "text": text}
        response = requests.Request(receive=params)
        response.post(url)

        return response.json()
