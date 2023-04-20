import os
import textwrap

import requests
from fastapi import APIRouter

from app.models.users import User, UserCustomer
from app.schemas.error import AlertMessage
from app.schemas.notification import Notification
from app.schemas.reponse import ResponseBody
from app.core.config import BotNotify, settings, BotNotifyV2
from app.utils.notification_service import get_all_subscribers, get_status, \
    customer_find_from_subscribers, send_batch_notification_to_topic_task_v2, send_batch_notification_to_topic_task, \
    send_batch_notification_to_topic_task_v3
from app.utils.celery_utils import get_task_info

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
        subscribers = await get_all_subscribers(topic=notification.topicName)
        print(subscribers)
        customers = await customer_find_from_subscribers(subscribers=subscribers)
        print(customers)
        try:
            text = f"*{notification.title}*\n{notification.body}"
            task_uuid = send_batch_notification_to_topic_task_v3.delay(subscribers=subscribers, text=text, bot=bot)
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
async def error_handler(error: AlertMessage):
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


@router.get("/{task_uuid}", response_model=ResponseBody, status_code=200)
async def get_task_status(task_uuid: str):
    return ResponseBody(status=0, data=get_task_info(task_uuid))
