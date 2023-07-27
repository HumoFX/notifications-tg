import logging
import os
import textwrap

import requests
from fastapi import APIRouter
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
from loguru import logger

router = APIRouter(prefix="/notification", tags=["notification"])
bot = BotNotify()


@router.post("/", response_model=ResponseBody, status_code=201)
async def create_task(notification: Notification):
    # if notification.topicName:
    #     try:
    #         text = f"*{notification.title}*\n{notification.body}"
    #         task_uuid = send_batch_notification_to_topic_task_v2.delay(topic=notification.topicName, text=text, bot=bot)
    #         return ResponseBody(status=0, data={"message": "success", "task_uuid": task_uuid.id})
    #     except Exception as e:
    #         return ResponseBody(status=1001, errorMessage=str(e))
    if notification.topicName:
        #     subscribers = await get_all_subscribers(topic=notification.topicName)
        #     print(subscribers)
        #     customers = await customer_find_from_subscribers(subscribers=subscribers)
        #     print(customers)
        try:
            text = f"*{notification.title}*\n{notification.body}"
            task_uuid = send_batch_notification_to_topic_task_v2.delay(topic=notification.topicName, text=text, bot=bot)
            return ResponseBody(status=0, data={"message": "success", "task_uuid": task_uuid.id})
        except Exception as e:
            return ResponseBody(status=1001, errorMessage=str(e))
    customer = await UserCustomer.get(notification.customerId)
    if customer:
        # message = await bot.send_message(customer.user_id, notification.body)
        text = f"*{notification.title}*\n{notification.body}"
        message = bot.sendMessage(customer.user_id, text, customer_id=customer.customer_id)
        if message.get("ok"):
            return ResponseBody(status=0, data={"message": "success"})
        elif message.get("error_code") == 404:
            return ResponseBody(status=1001, errorMessage="User not found")
        else:
            return ResponseBody(status=1001, errorMessage="Failed to send message")
    else:
        return ResponseBody(status=2000, errorMessage="Customer not found")


@router.post("/test")
async def test_notification(token: str, chat_id: str, text: str):
    # send request to api telegram org bot
    # https://api.telegram.org/bot<token>/sendMessage?chat_id=<chat_id>&text=<text>
    api_url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}"
    response = requests.post(api_url, headers={"Content-Type": "application/json"})
    return response.json()


@router.post('/errors', response_model=ResponseBody, status_code=200)
async def error_handler(error: AlertMessageV2):
    message = await bot.send_alert_message(error)
    if message:
        if message.get('ok'):
            return ResponseBody(status=0, data={"message": "success"})
        elif message.get("error_code") == 404:
            return ResponseBody(status=1000, errorMessage="User not found")
        else:
            return ResponseBody(status=1001, errorMessage="Failed to send message")
    else:
        return ResponseBody(status=1002, errorMessage="Failed to send message")


@router.post('/face_id_error', response_model=ResponseBody, status_code=200)
async def error_handler_v2(error: AlertMessageV2):
    # save to redis for 48 hours
    # get redis data by key
    data = await redis().get(error.pinfl)
    str_date_now = str(datetime.datetime.now())
    error_code_key = f"{error.tag}_{error.errorCode}"
    last_message_id = None
    if data:
        data = json.loads(data)
        logger.info(f"redis data: {data}")
        if error_code_key in data.keys():
            last_message_id = data[error_code_key].get('last_message_id')
            data[error_code_key]['error_message'] = error.errorMessage
            data[error_code_key]['created_at'] = str_date_now
            data[error_code_key]['try_count'] = data[error_code_key]['try_count'] + 1 if data[error_code_key].get(
                'try_count') else 1
            tries_date = data[error_code_key].get('tries_date') if data[error_code_key].get('tries_date') else []
            tries_date += [str_date_now]
            data[error_code_key]['tries_date'] = tries_date
        else:
            data[error_code_key] = {
                'error_message': error.errorMessage,
                'created_at': str_date_now,
                'try_count': 1,
                'tries_date': [str_date_now]
            }
        # data = json.dumps(data, ensure_ascii=False, indent=4)
        # logger.info(f"new data: {data}")
        # try:
        #     await redis().setex(name=error.pinfl, time=604800, value=data)
        # except Exception as e:
        #     logger.error(f"error: {e}")
    else:
        data = {
            error_code_key: {
                'error_message': error.errorMessage,
                'created_at': str_date_now,
                'try_count': 1,
                'tries_date': [str_date_now]
            }
        }
        # data = json.dumps(data, ensure_ascii=False, indent=4)
        # try:
        #     await redis().setex(name=error.pinfl, time=604800, value=data)
        # except Exception as e:
        #     logger.error(f"error: {e}")
    # return ResponseBody(status=0, data={"message": "success"})
    logger.info(f"last_message_id: {last_message_id}")
    message = await bot.send_alert_message_v2(error, reply_to_message_id=last_message_id, try_count=data[error_code_key].get('try_count'))
    if message:
        if message.get('ok'):
            # create FaceIDAlert
            created_at = datetime.datetime.now()

            await FaceIDAlert.create(
                message_id=message.get("result").get("message_id"),
                type=error.system,
                topic=error.tag,
                pinfl=error.pinfl,
                error_code=error.errorCode,
                error_message=error.errorMessage,
                created_at=created_at)
            data[error_code_key]["message_ids"] = data[error_code_key].get("message_ids", [])
            data[error_code_key]["message_ids"].append(message.get("result").get("message_id"))
            data[error_code_key]["last_message_text"] = message.get("result").get("text")
            data[error_code_key]["last_message_id"] = message.get("result").get("message_id")
            data = json.dumps(data, ensure_ascii=False, indent=4)
            try:
                await redis().set(name=error.pinfl, value=data)
            except Exception as e:
                logger.error(f"error: {e}")
            try:
                # edit last message - remove keyboard
                logger.info(f"last_message_id 2: {last_message_id} {error.tag}")
                msg = await bot.edit_message_reply_markup(message_id=last_message_id, message_thread_id=error.tag)
                logger.info(f"edit message: {msg}")
            except Exception as e:
                logger.error(f"error: {e}")

            return ResponseBody(status=0, data={"message": "success"})
        elif message.get("error_code") == 404:
            return ResponseBody(status=1000, errorMessage="User not found")
        else:
            logger.error(f"message: {message}")
            return ResponseBody(status=1001, errorMessage=f"Failed to send message. {message.get('description')}")
    else:
        return ResponseBody(status=1002, errorMessage="Failed to send message")


@router.get("/{task_uuid}", response_model=ResponseBody, status_code=200)
async def get_task_status(task_uuid: str):
    return ResponseBody(status=0, data=get_task_info(task_uuid))
