import json
import os
import re
import textwrap

import requests
from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse, ujson
import asyncio
import aiohttp
from pydantic import BaseSettings, EmailStr, SecretStr, validator

from app.schemas.error import AlertMessage


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
    ALERT_BOT_TOKEN: str
    ALERT_CHANNEL_ID: str
    proxy = {"http": "http://192.168.152.200:8080", "https": "http://192.168.152.200:8080"}

    def get_bot_token(self):
        self.BOT_TOKEN = os.environ.get("BOT_TOKEN")
        return self.BOT_TOKEN

    def get_alert_bot_token(self):
        self.BOT_TOKEN = os.environ.get("ALERT_BOT_TOKEN")
        return self.BOT_TOKEN

    def get_alert_channel_id(self):
        self.ALERT_CHANNEL_ID = os.environ.get("ALERT_CHANNEL_ID")
        return self.ALERT_CHANNEL_ID

    def get_telegram_url(self):
        return "https://api.telegram.org/bot{}/".format(self.BOT_TOKEN)

    def get_alert_url(self):
        return "https://api.telegram.org/bot{}/".format(self.ALERT_BOT_TOKEN)

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()


# create dataclass for telegram bot with token , url and sendMessage method


async def post(url, headers, proxy, **kwargs):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=kwargs, proxy=proxy.get('http')) as response:
                data = await response.json()
                return data
        except Exception as err:
            pass
            # logger.exception(f"Error in post {err}")


class BotNotify:
    def __init__(self):
        self.token = settings.BOT_TOKEN
        self.url = "https://api.telegram.org/bot{}/".format(self.token)
        self.alert_url = "https://api.telegram.org/bot{}/".format(settings.ALERT_BOT_TOKEN)
        self.alert_channel = settings.ALERT_CHANNEL_ID

    async def send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML'):
        url = self.url + "sendMessage?chat_id={}&text={}&parse_mode={}".format(chat_id, text, parse_mode)
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy)
        return response

    async def send_alert_message(self, error: AlertMessage):
        text = f"<i>🚨 {error.criticalityLevel}</i>\n"
        text += f"<b>{error.errorName}</b>\n"
        text += f"<pre>Код ошибки: {error.errorCode}</pre>\n"
        if error.section:
            text += f"<pre>Раздел: {error.section}</pre>\n"
        if error.operation:
            text += f"<pre>Операции: {error.operation}</pre>\n"
        if error.operationStatus:
            text += f"<pre>Статус операции: {error.operationStatus}</pre>\n"
        if error.operationCodeIFB:
            text += f"<pre>Код операции IFB: {error.operationCodeIFB}</pre>\n"
        if error.operationCodeABS:
            text += f"<pre>Код операции АБС: {error.operationCodeABS}</pre>\n"
        if error.tag:
            text += f"#{error.tag}\n"

        text = textwrap.dedent(text)
        data = {
            "chat_id": self.alert_channel,
            "text": text,
            "parse_mode": "HTML",
        }
        url = self.alert_url + "sendMessage"
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response

    def sendMessage(self, chat_id: int, text: str, customer_id: int):
        markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "Мои заявки",
                        "callback_data": "my_app: {customer_id}".format(customer_id=customer_id),
                    },
                ]
            ]
        }
        # markup = json.dumps(markup)
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": markup,
        }
        url = self.url + "sendMessage"
        # response = requests.post(url=url, data=data)

        # url = self.url + "sendMessage?chat_id={}&text={}&parse_mode=Markdown".format(chat_id, text)
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=data, proxies=settings.proxy)
        return response.json()

    async def send_sms_info(self, chat_id, text):
        codes = re.findall(r"\b\d+\b", text)
        if len(codes) == 1:
            text = text.replace(codes[0], f"<pre>{codes[0]}</pre>")
        message = f"💬 {text}"
        return await self.send_message(chat_id, message)







