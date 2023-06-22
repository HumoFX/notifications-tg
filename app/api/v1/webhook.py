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
from loguru import logger

router = APIRouter(prefix="/webhook", tags=["telegram"])
bot = BotNotify()


async def get_webhook_info():
    webhook_info = bot.get_webhook_info()
    return webhook_info


async def callback_query_handler(callback_query):

    pass


@router.post("/")
async def telegram_webhook(request: Request):
    logger.info(request)
    data = await request.json()
    logger.info(data)
    return {"status": "ok"}
