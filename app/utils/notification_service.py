import aiohttp
import asyncio
import uuid
from app.core.config import settings, BotNotify, BotNotifyV2
from app.core.redis import create_redis_pool as redis
from app.models.users import UserCustomer
from celery import shared_task
from time import sleep
from app.core.database import db

tasks = {}
loop = asyncio.new_event_loop()


async def get_topic_subscribers(topic: str, page: int = 1):
    """
    Getting Topic Subscribers from api
    :param topic: str
    :param page: int
    :return:
    """

    async with aiohttp.ClientSession() as session:
        url = settings.BASE_URL + "/notification/get/subscribers"
        headers = {}
        payload = {
            "topicName": topic,
            "page": page
        }
        async with session.post(url, headers=headers, json=payload) as response:

            if response.status == 200:
                if await response.json():
                    return await response.json()
            return None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True,
             retry_kwargs={"max_retries": 5}, name='notifications:get_all_subscribers')
async def get_all_subscribers(self, topic: str):
    # increment page and get topic subscribers while response is not empty
    page = 1
    subscribers = []
    while True:
        response = await get_topic_subscribers(topic, page)
        if response and response.get("data"):
            subscribers.extend(response.get("data"))
            page += 1
        else:
            break
    return subscribers


async def customer_find_from_subscribers(subscribers: list):
    # find customer from subscribers
    customers = []
    for subscriber in subscribers:
        customer = await UserCustomer.get(subscriber.get("customerId"))
        if customer:
            customers.append(customer)
    return customers


@shared_task(bind=True, name='notifications:send_batch_notification_to_topic_task')
def send_batch_notification_to_topic_task(self, subscribers: list, text: str, bot: BotNotify):
    success = 0
    failed = 0
    self.update_state(state="PROGRESS", meta={"progress": "get customers"})
    for subscriber in subscribers:
        message = bot.sync_send_message(chat_id=subscriber.user_id, text=text)
        if message.get("ok"):
            success += 1
        else:
            failed += 1
        sleep(0.05)
        self.update_state(state="PROGRESS",
                          meta={"progress": f"send notification to {subscriber.user_id}",
                                "success": success, "failed": failed, "total": len(subscribers)})
    return {"success": success, "failed": failed, "total": len(subscribers)}


async def get_user_by_customer_id(customer_id: int):
    async with db.with_bind(settings.POSTGRES_URI) as conn:
        customer = await UserCustomer.query.where(UserCustomer.customer_id == customer_id).gino.first()
        return customer


@shared_task(bind=True, name='notifications:send_batch_notification_to_topic_task_v2')
def send_batch_notification_to_topic_task_v2(self, topic: str, text: str, bot: BotNotify):
    page = 1
    subscribers = []
    self.update_state(state="PROGRESS", meta={"progress": "get subscribers", "page": page, "total": 0})
    while True:
        response = loop.run_until_complete(get_topic_subscribers(topic, page))
        if response and response.get("data"):
            subscribers.extend(response.get("data"))
            page += 1
            self.update_state(state="PROGRESS",
                              meta={"progress": "get subscribers", "page": page, "total": len(subscribers)})
        else:
            break
    success = 0
    failed = 0
    self.update_state(state="PROGRESS", meta={"progress": "get customers", "total": len(subscribers)})
    customers = []

    if not subscribers:
        self.update_state(state="FAILURE", meta={"progress": "subscribers not found or failed to get"})
        return {"success": success, "failed": failed, "total": len(subscribers)}
    for subscriber in subscribers:
        customer = loop.run_until_complete((get_user_by_customer_id(subscriber.get("customerId"))))
        if customer:
            customers.append(customer)
    if not customers:
        self.update_state(state="FAILURE", meta={"progress": "customers not found"})
        return {"success": success, "failed": failed, "total": len(subscribers)}

    for customer in customers:
        message = bot.sync_send_message(chat_id=customer.user_id, text=text)
        if message.get("ok"):
            success += 1
        else:
            failed += 1
        sleep(0.05)
        self.update_state(state="PROGRESS",
                          meta={"progress": f"send notification to {customer.user_id}",
                                "success": success, "failed": failed, "total": len(customers)})
    return {"success": success, "failed": failed, "total": len(subscribers)}


async def get_status(task_uuid: str):
    # get task status
    task = tasks.get(task_uuid)

    if task:
        result = task.result()
        if task.done():
            result["status"] = "done"
        else:
            result["status"] = "pending"
        return result
    else:
        return {"status": "not found"}
