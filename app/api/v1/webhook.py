import logging
import os
import textwrap

import requests
from fastapi import APIRouter, Request
import datetime
import pickle
import json
from app.models.users import User, UserCustomer
from app.models.alert import FaceIDAlert
from app.schemas.error import AlertMessage, AlertMessageV2
from app.schemas.notification import Notification
from app.schemas.reponse import ResponseBody
from app.core.config import BotNotify, settings, BotNotifyV2
from app.utils.notification_service import get_all_subscribers, get_status, \
    customer_find_from_subscribers, send_batch_notification_to_topic_task_v2, send_batch_notification_to_topic_task, \
    send_batch_notification_to_topic_task_v3
from app.utils.celery_utils import get_task_info
from app.core.redis import create_redis_pool as redis
from asyncio import gather
from loguru import logger

router = APIRouter(prefix="/webhook", tags=["telegram"])
bot = BotNotify()


async def get_webhook_info():
    webhook_info = bot.get_webhook_info()
    return webhook_info


# async def report_to_xls():
#     from xlsxwriter import Workbook
#     pass


async def command_handler(message: str, message_thread_id: int):
    command = message.split(" ")[0]
    if command == "/report":
        pass


async def callback_query_handler(callback_query: dict, message_thread_id: int, key: str, value: str):
    if key == "f_id_er":
        pinfl = value.split("_")[0]
        error_code = value.split("_")[1]
        redis_data = await redis().get(pinfl)
        error_code_key = f"{message_thread_id}_{error_code}"
        if not redis_data:
            redis_data = b'{}'
        data = json.loads(redis_data)
        if data.get(error_code_key):
            # delete all messages from thread id except last message
            message_ids = data[error_code_key].get("message_ids")
            failed = 0
            if len(message_ids) > 1:
                tasks = []
                for item in message_ids[:-1]:
                    tasks.append(bot.delete_message(message_id=item, message_thread_id=message_thread_id))
                results = await gather(*tasks)
                for item in results:
                    if not item.get("ok"):
                        failed += 1
            # edit last message


            message_id = message_ids[-1]
            text = data[error_code_key].get("last_message_text")
            alert_text = ""
            if failed >= 1:
                alert_text += f"Не удалось удалить {failed} сообщений с ошибкой {error_code} для ПИНФЛ {pinfl}"
            text += f"\n\n✅ Исправлено"
            edited = await bot.edit_message_text(message_id=message_id, text=text,
                                                 message_thread_id=message_thread_id)
            if not edited.get("ok"):
                logger.error(f"Error: {edited}")
                alert_text += f"\n Не удалось отредактировать сообщение с ошибкой {error_code} для ПИНФЛ {pinfl}"
            if alert_text:
                alert_text += "Статус исправления ошибки в базе данных: исправлено"
                msg = await bot.answer_callback_query(text=alert_text, callback_query_id=callback_query.get("id"),
                                                      alert=True)
                resp = await bot.update_auth_limit(pinfl=pinfl)
                if resp:
                    if resp.get("data"):
                        alert_text += f"Увеличен лимит попытки авторизации"
                    elif resp.get("errorMessage"):
                        alert_text += f"{resp.get('errorMessage')}"
                else:
                    alert_text += f"Не удалось увеличить лимит попытки авторизации"
                logger.info(f"alert_text: {msg}")
            logger.info(f"edited message {message_id} {edited}")
            # data[error_code] delete from redis
            del data[error_code_key]
            await redis().set(pinfl, json.dumps(data))
        else:
            logger.error(f"Error: {error_code_key} not found in redis")

    if key == "ask_confirm":
        pinfl = value.split("_")[0]
        error_code = value.split("_")[1]
        redis_data = await redis().get(pinfl)
        error_code_key = f"{message_thread_id}_{error_code}"
        if not redis_data:
            redis_data = b'{}'
        data = json.loads(redis_data)
        message_id = callback_query.get("message").get("message_id")
        logger.info(f"message_id: {message_id}")
        if data.get(error_code_key):
            text = data[error_code_key].get("last_message_text")
            text += f"\n\n"
            text += "<b>Вы уверены, что хотите подтвердить исправление ошибки?</b>\n" \
                    "<i>(Будут удалены все сообщения, кроме последнего)</i>"
            callback_data = f"{pinfl}_{error_code}"
            send_confirm = await bot.send_confirm_message(message_id=message_id, text=text,
                                                          message_thread_id=message_thread_id,
                                                          callback_data=callback_data, parse_mode="HTML")
            logger.info(f"send_confirm: {send_confirm}")
    if key == "cancel":
        pinfl = value.split("_")[0]
        error_code = value.split("_")[1]
        logger.info(f"pinfl: {pinfl}, error_code: {error_code}")
        redis_data = await redis().get(pinfl)
        error_code_key = f"{message_thread_id}_{error_code}"
        if not redis_data:
            redis_data = b'{}'
        data = json.loads(redis_data)
        message_id = callback_query.get("message").get("message_id")
        if data.get(error_code_key):
            text = data[error_code_key].get("last_message_text")
            callback_data = f"ask_confirm:{pinfl}_{error_code}"
            send_conf_message = await bot.send_confirm_message(message_id=message_id, text=text, confirm=False,
                                                               message_thread_id=message_thread_id,
                                                               callback_data=callback_data)
            logger.info(f"send_conf_message: {send_conf_message}")
            if not send_conf_message.get("ok") and send_conf_message.get("error_code") == 400:
                text = "Произошла ошибка: \n"
                text += send_conf_message.get("description")
                await bot.answer_callback_query(text=text, message_thread_id=message_thread_id, alert=True)


@router.post("/")
async def telegram_webhook(request: Request):
    logger.info(request)
    data = await request.json()
    logger.info(data)
    callback_query = data.get("callback_query")
    message = data.get("message")
    is_command = message and message.get("text") and message.get("text").startswith("/")
    if message and is_command:
        message_thread_id = message.get("message_thread_id")
        text = message.get("text")
        logger.info(f"message_thread_id: {message_thread_id}, text: {text}")
        await command_handler(text, message_thread_id)
    if callback_query:
        message_thread_id = data["callback_query"]["message"].get("message_thread_id")
        data = callback_query.get("data")
        key = data.split(":")[0]
        value = data.split(":")[1]
        logger.info(f"key: {key}, value: {value}, message_thread_id: {message_thread_id}")
        await callback_query_handler(callback_query, message_thread_id, key, value)
    return {"status": "ok"}
