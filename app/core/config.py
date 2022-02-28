import os
import requests
from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse, ujson
import asyncio
import aiohttp
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

    # FIRST_USER_EMAIL: EmailStr
    # FIRST_USER_PASSWORD: SecretStr

    # SECRET_KEY: SecretStr
    # ACCESS_TOKEN_EXPIRE_MINUTES: int

    # REDIS_HOST: str
    # REDIS_PORT: int

    BOT_TOKEN: str
    proxy = {"http": "http://192.168.152.200:8080"}

    def get_bot_token(self):
        self.BOT_TOKEN = os.environ.get("BOT_TOKEN")
        return self.BOT_TOKEN

    def get_telegram_url(self):
        return "https://api.telegram.org/bot{}/".format(self.BOT_TOKEN)

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()

# create dataclass for telegram bot with token , url and sendMessage method


async def post(url, headers, **kwargs):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=kwargs) as response:
                status = response.status
                if status == 200:
                    data = await response.json()
                    return data
        except Exception as err:
            print(err)
            pass
            # logger.exception(f"Error in post {err}")


class BotNotify:
    def __init__(self):
        self.token = settings.BOT_TOKEN
        self.url = "https://api.telegram.org/bot{}/".format(self.token)

    def send_message(self, chat_id: int, text: str):
        url = self.url + "sendMessage?chat_id={}&text={}".format(chat_id, text)
        print(url)
        response = post(url, {"Content-Type": "application/json"})
        print(response)
        return response

    def sendMessage(self, chat_id: int, text: str):
        url = self.url + "sendMessage?chat_id={}&text={}".format(chat_id, text)
        response = requests.post(url, headers={"Content-Type": "application/json"},
                                 proxies=settings.proxy, verify=False)
        return response.json()

