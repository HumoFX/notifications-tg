import logging
import os
import textwrap

import requests
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import KeyboardBuilder
from fastapi import APIRouter, Request
import datetime
import pickle
import json

from sqlalchemy import and_

from app.core.database import db
from app.models.users import User, UserCustomer
from app.models.alert import FaceIDAlert, FaceIdAdmin
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
async def report_handler(message_thread_id: int, chat_id: int = None):
    text = "Выберите период"
    keyboard = report_inline_buttons()
    dict_keyboard = keyboard.to_python()
    start_date = datetime.datetime.now() - datetime.timedelta(days=3)
    end_date = datetime.datetime.now()
    file_path = await export_alert_data_for_period_xls(start_date, end_date)
    logger.info(f"file_path: {file_path}")
    if file_path:
        with open(file_path, "rb") as file:
            resp = await bot.send_file(chat_id=chat_id, file=file)
            logger.info(f"resp: {resp}")
    await bot.send_message_v3(text=text, chat_id=chat_id, message_thread_id=message_thread_id,
                              reply_markup=dict_keyboard)


async def command_handler(message: str, message_thread_id: int, chat_id: int = None):
    command = message.split(" ")[0]
    if command == "/report":
        await report_handler(message_thread_id, chat_id=chat_id)


async def has_admin_perm(user_id: int, permission_tag) -> bool:
    has_access = False
    if user_id:
        user = await FaceIdAdmin.get(user_id)
        logger.info(f"access user data {user} {user}")
        if user:
            permissions = user.data.get("tags", [])
            has_access = True if permission_tag in permissions else False
        return has_access


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
            user_id = callback_query["from"].get("id")
            user = await FaceIdAdmin.get(user_id)
            if user:
                text += f"\n\n✅ Исправлено\n👨🏻‍💻{user.first_name} {user.last_name}"
            else:
                text += f"\n\n✅ Исправлено\n👨🏻‍💻#{user_id}"
            edited = await bot.edit_message_text(message_id=message_id, text=text,
                                                 message_thread_id=message_thread_id)
            face_id_alert = data[error_code_key].get("face_id_alert")
            if face_id_alert:
                await FaceIDAlert.update.values(face_id_admin=user_id).where(
                    FaceIDAlert.id == face_id_alert).gino.status()
            else:
                logger.error(f"Error: face_id_alert not found {face_id_alert}")
            if not edited.get("ok"):
                logger.error(f"Error: {edited}")
                alert_text += f"\n Не удалось отредактировать сообщение с ошибкой {error_code} для ПИНФЛ {pinfl}"
            resp = await bot.update_auth_limit(pinfl=pinfl)
            if resp:
                if resp.get("data"):
                    alert_text += f"Увеличен лимит попытки авторизации"
                elif resp.get("errorMessage"):
                    alert_text += f"{resp.get('errorMessage')}"
            else:
                alert_text += f"Не удалось увеличить лимит попытки авторизации"
            if alert_text:
                # alert_text += "Статус исправления ошибки в базе данных: исправлено"
                msg = await bot.answer_callback_query(text=alert_text, callback_query_id=callback_query.get("id"),
                                                      alert=True)
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
                    "<i>Обновиться лимит попыток для авторизации(Будут удалены все сообщения, кроме последнего)</i>"
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
                await bot.answer_callback_query(text=text, alert=True,
                                                callback_query_id=callback_query.get("id"))


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
        chat_id = message.get("chat").get("id")
        text = message.get("text")
        logger.info(f"message_thread_id: {message_thread_id}, text: {text}")
        await command_handler(text, message_thread_id, chat_id=chat_id)
    if callback_query:
        from_user = callback_query.get("from")
        user_id = from_user.get("id")
        message_thread_id = data["callback_query"]["message"].get("message_thread_id")
        data = callback_query.get("data")
        key = data.split(":")[0]
        value = data.split(":")[1]
        logger.info(f"key: {key}, value: {value}, message_thread_id: {message_thread_id}")
        has_perm = await has_admin_perm(user_id=user_id, permission_tag=message_thread_id)
        if not has_perm:
            text = "У вас нет доступа"
            await bot.answer_callback_query(text=text, alert=True, callback_query_id=callback_query.get("id"))
        else:
            await callback_query_handler(callback_query, message_thread_id, key, value)
    return {"status": "ok"}


def get_days_in_month(year, month):
    import calendar
    return calendar.monthrange(year, month)[1]


def inline_calendar():
    import datetime
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day
    days = get_days_in_month(current_year, current_month)
    keyboard = InlineKeyboardMarkup(row_width=7)
    for day in range(1, days + 1):
        keyboard.add(InlineKeyboardButton(text=str(day), callback_data=f"DAY-{day}"))
    keyboard.row(InlineKeyboardButton(text="Предыдущий месяц", callback_data="PREV-MONTH"),
                 InlineKeyboardButton(text="Следующий месяц", callback_data="NEXT-MONTH"))
    return keyboard


def get_calendar():
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day
    days = get_days_in_month(current_year, current_month)
    keyboard = InlineKeyboardMarkup(row_width=7)
    keyboard.add(InlineKeyboardButton(text="Предыдущий месяц", callback_data="PREV-MONTH"),
                 InlineKeyboardButton(text="Следующий месяц", callback_data="NEXT-MONTH"))
    keyboard.add(InlineKeyboardButton(text="Пн", callback_data="MON"),
                 InlineKeyboardButton(text="Вт", callback_data="TUE"),
                 InlineKeyboardButton(text="Ср", callback_data="WED"),
                 InlineKeyboardButton(text="Чт", callback_data="THU"),
                 InlineKeyboardButton(text="Пт", callback_data="FRI"),
                 InlineKeyboardButton(text="Сб", callback_data="SAT"),
                 InlineKeyboardButton(text="Вс", callback_data="SUN"))
    for day in range(1, days + 1):
        keyboard.add(InlineKeyboardButton(text=str(day), callback_data=f"DAY-{day}"))
    return keyboard


def get_calendar_v2():
    # Build keyboard
    keyboard = KeyboardBuilder()
    keyboard.add("Предыдущий месяц", "Следующий месяц")


def report_inline_buttons():
    keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[])
    keyboard.add(InlineKeyboardButton(text="Час", callback_data="HOURLY"),
                 InlineKeyboardButton(text="День", callback_data="DAILY"),
                 InlineKeyboardButton(text="Неделя", callback_data="WEEKLY"),
                 InlineKeyboardButton(text="Период", callback_data="PERIOD"))
    return keyboard


async def get_alert_data_for_period(start_date: datetime.datetime, end_date: datetime.datetime) -> list[FaceIDAlert]:
    # face_id_alerts_with_face_id_admin = await FaceIDAlert.query.where(and_(FaceIDAlert.created_at >= start_date,
    # FaceIDAlert.created_at <= end_date,)).leftJoin( FaceIdAdmin).select().gino.all() face_id_alert_grouped_by_pinfl
    # = await FaceIDAlert.query.where(and_(FaceIDAlert.created_at >= start_date, FaceIDAlert.created_at <= end_date,
    # )).group_by( FaceIDAlert.pinfl).select().gino.all()
    face_id_alert_group_by_message_with_count = await db.select([FaceIDAlert.error_code, FaceIDAlert.type,
                                                                 FaceIDAlert.error_message, db.func.count(
            FaceIDAlert.error_message).label("count")]).where(and_(FaceIDAlert.created_at >= start_date,
                                                                   FaceIDAlert.created_at <= end_date)).group_by(
        FaceIDAlert.error_message).gino.all()

    return face_id_alert_group_by_message_with_count


async def export_alert_data_for_period_xls(start_date: datetime.datetime, end_date: datetime.datetime):
    face_id_alerts_with_face_id_admin: list[FaceIDAlert] = await get_alert_data_for_period(start_date, end_date)
    logger.info(face_id_alerts_with_face_id_admin)
    import xlsxwriter
    import uuid
    file_name = f"{uuid.uuid4().hex}.xlsx"
    dir = os.path.join(os.getcwd(), "reports")
    if not os.path.exists(dir):
        os.mkdir(dir)
    file_path = os.path.join(dir, file_name)
    workbook = xlsxwriter.Workbook(file_path)
    worksheet = workbook.add_worksheet()
    worksheet.write(0, 0, "Код ошибки")
    worksheet.write(0, 1, "Название операции")
    worksheet.write(0, 2, "Описание")
    worksheet.write(0, 3, "Количество")
    for index, alert in enumerate(face_id_alerts_with_face_id_admin):
        error_code = alert.error_code
        error_type = alert.type
        error_message = alert.error_message
        count = alert.count
        worksheet.write(index + 1, 0, error_code)
        worksheet.write(index + 1, 1, error_type)
        worksheet.write(index + 1, 2, error_message)
        worksheet.write(index + 1, 3, count)
    workbook.close()
    # send file to telegram chat id
    return file_path
