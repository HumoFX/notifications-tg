import aiohttp
import asyncio
import uuid
from app.core.config import settings, BotNotify
from app.models.users import UserCustomer

tasks = {}


async def get_topic_subscribers(topic: str, page: int = 1):
    """
    Getting Topic Subscribers from api
    :param topic: str
    :param page: int
    :return:
    """

    async with aiohttp.ClientSession() as session:
        url = settings.BASE_URL + ""
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

async def get_all_subscribers(topic: str):
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

async def customer_find_from_subscribers(subscribers: list):
    # find customer from subscribers
    customers = []
    for subscriber in subscribers:
        customer = await UserCustomer.get(subscriber.get("customerId"))
        if customer:
            customers.append(customer.user_id)
    return customers

async def send_batch_notification_to_topic_task(subscribers: list, message: str, bot: BotNotify):
    success = 0
    failed = 0
    subscribers = await customer_find_from_subscribers(subscribers)
    for subscriber in subscribers:
        # send notification to subscriber
        message = await bot.send_message(subscriber.user_id, message)
        if message.get("ok"):
            success += 1
        else:
            failed += 1
        # sleep for 0.5 seconds
        await asyncio.sleep(0.05)
        # save to task result
        yield {"success": success, "failed": failed, "total": len(subscribers)}


async def get_status(task_uuid: str):
    # get task status
    task = tasks.get(task_uuid)
    if task:
        result = task.result()
        if task.done():
            result["status"] = "done"
        else:
            result["status"] = "pending"
        print(result)
        return result
    else:
        return {"status": "not found"}


async def send_notification_to_topic(subscribers: list, message: str):
    # run send_batch_notification_to_topic as task
    bot = BotNotify()
    task_uuid = str(uuid.uuid4())
    task = asyncio.create_task(send_batch_notification_to_topic(subscribers, message, bot))
    tasks[task_uuid] = task
    return task_uuid
