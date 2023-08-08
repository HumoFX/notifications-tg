import datetime
import json
import os
import re
import textwrap

import requests
from dataclasses import dataclass
from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse, ujson
import asyncio
import aiohttp
from pydantic import BaseSettings, EmailStr, SecretStr, validator

from app.schemas.error import AlertMessage, AlertMessageV2
import os
from functools import lru_cache
from kombu import Queue
from loguru import logger


def route_task(name, args, kwargs, options, task=None, **kw):
    if ":" in name:
        queue, _ = name.split(":")
        return {"queue": queue}
    return {"queue": "celery"}


class Settings(BaseSettings):
    PROJECT_NAME: str

    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_URI: Optional[str] = None
    BASE_URL: str

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

    REDIS_HOST: str
    REDIS_PORT: int

    BOT_TOKEN: str
    ALERT_BOT_TOKEN: str
    ALERT_CHANNEL_ID: str
    NEW_ALERT_GROUP_ID: str
    proxy = {"http": "http://192.168.152.200:8080", "https": "http://192.168.152.200:8080"}
    # proxy = {}

    CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
    CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")

    CELERY_TASK_QUEUES: list = (
        # default queue
        Queue("notifications"),
    )

    CELERY_TASK_ROUTES = (route_task,)

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
        self.back_prod = "https://dbop.infinbank.com:9443/api/v2/"
        self.alert_channel = settings.ALERT_CHANNEL_ID
        self.alert_group = settings.NEW_ALERT_GROUP_ID

    async def send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML'):
        url = self.url + "sendMessage?chat_id={}&text={}&parse_mode={}".format(chat_id, text, parse_mode)
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy)
        return response

    async def send_message_v2(self, text: str, message_thread_id: int, alert: bool = False, parse_mode: str = 'HTML'):
        chat_id = self.alert_group
        url = self.url + "sendMessage?chat_id={}&text={}&parse_mode={}".format(chat_id, text, parse_mode)
        if alert:
            url += "&showAlert=true"
        if message_thread_id:
            url += "&message_thread_id={}".format(message_thread_id)
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy)
        return response

    def sync_send_message(self, chat_id: str, text: str, parse_mode: str = 'Markdown'):
        headers = requests.utils.default_headers()
        headers.update(
            {
                'User-Agent': 'My User Agent 1.0',
            }
        )
        url = self.url + "sendMessage?chat_id={}&text={}&parse_mode={}".format(chat_id, text, parse_mode)
        response = requests.post(url, headers=headers, proxies=settings.proxy)
        return response.json()

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

    async def send_alert_message_v2(self, error: AlertMessageV2, reply_to_message_id: int = None,
                                    try_count: int = 0):
        data_key = f"ask_confirm:{error.pinfl}_{error.errorCode}"
        if len(data_key) > 64:
            data_key = data_key[:64]
        markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Проблема решена",
                        "callback_data": data_key,
                    },
                ]
            ]
        }
        text = f"<i>🚨 {error.criticalityLevel}</i>\n"
        text += f"<b>💬 {error.errorMessage}</b>\n"
        created_date = datetime.datetime.now().strftime("%H:%M:%S %Y-%m-%d")
        text += f"🔍 Код ошибки: {error.errorCode}\n"
        if error.system:
            text += f"📍 Система: <b>{error.system}</b>\n"
        if error.pinfl:
            text += f"🆔 ПИНФЛ: <pre>{error.pinfl}</pre>\n"
        text += f"🕓 {created_date}\n"
        if try_count and try_count > 1:
            text += f"🔁 Попытка №{try_count}\n"

        text = textwrap.dedent(text)
        data = {
            "chat_id": self.alert_group,
            "text": text,
            "message_thread_id": error.tag,
            "parse_mode": "HTML",
            "reply_markup": markup,
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        url = self.alert_url + "sendMessage"
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        if reply_to_message_id and response.get("ok") is False:
            # retry without reply_to_message_id
            data.pop("reply_to_message_id")
            response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response

    async def send_confirm_message(self, text: str, message_id: int, message_thread_id: int,
                                   parse_mode: str = 'Markdown',
                                   confirm: bool = True, callback_data: str = None):
        if confirm:
            markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Подтвердить",
                            "callback_data": f"f_id_er:{callback_data}",
                        },
                        {
                            "text": "❌ Отменить",
                            "callback_data": f"cancel:{callback_data}"
                        }
                    ]
                ]
            }
        else:
            markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Проблема решена",
                            "callback_data": callback_data,
                        },
                    ]
                ]
            }
        # markup = json.dumps(markup)
        data = {
            "chat_id": self.alert_group,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": markup,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
        }
        url = self.alert_url + "editMessageText"
        logger.info(f"send_confirm_message: {data}")
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
            # "reply_markup": markup,
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

    def get_webhook_info(self):
        url = self.url + "getWebhookInfo"
        response = requests.get(url, proxies=settings.proxy)
        return response.json()

    async def edit_message_text(self, message_id: int, text: str, parse_mode: str = 'HTML',
                                message_thread_id: int = None):
        # add text "resolved" to message and remove inline keyboard
        url = self.alert_url + "editMessageText"
        data = {
            "chat_id": self.alert_group,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": {"inline_keyboard": []},
        }
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response

    async def edit_message_reply_markup(self, message_id: int, message_thread_id: int = None):
        # remove inline keyboard
        url = self.alert_url + "editMessageReplyMarkup"
        data = {
            "chat_id": self.alert_group,
            "message_id": message_id,
            "reply_markup": {"inline_keyboard": []},
        }
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        logger.info(f"edit_message_reply_markup: {data}")
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response

    async def answer_callback_query(self, callback_query_id: str, text: str,
                                    alert: bool = False, message_thread_id: int = None):
        url = self.alert_url + "answerCallbackQuery"
        data = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": alert,
        }
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        logger.info(f"answer_callback_query: {data}")
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response

    async def delete_message(self, message_id: int, message_thread_id: int = None):
        url = self.alert_url + "deleteMessage"
        data = {
            "chat_id": self.alert_group,
            "message_id": message_id,
        }
        if message_thread_id:
            data["message_thread_id"] = message_thread_id
        logger.info(f"delete_message: {data}")
        response = await post(url, {"Content-Type": "application/json"}, proxy=settings.proxy, **data)
        return response


    async def update_auth_limit(self, pinfl):
        url = self.back_prod + "auth/limit/update"
        data = {
            "pinfl": pinfl
        }
        response = await post(url, {"Content-Type": "application/json"}, proxy={}, **data)
        return response



@dataclass
class BotNotifyV2:
    token: str = settings.BOT_TOKEN
    url: str = "https://api.telegram.org/bot{}/".format(settings.BOT_TOKEN)
    alert_url: str = "https://api.telegram.org/bot{}/".format(settings.ALERT_BOT_TOKEN)
    alert_channel: str = settings.ALERT_CHANNEL_ID

    def sync_send_message(self, chat_id: str, text: str, parse_mode: str = 'HTML'):
        url = self.url + "sendMessage?chat_id={}&text={}&parse_mode={}".format(chat_id, text, parse_mode)
        response = requests.post(url, headers={"Content-Type": "application/json"}, proxies=settings.proxy)
        return response.json()
