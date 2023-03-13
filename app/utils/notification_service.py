import aiohttp
from app.core.config import settings


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
    # increment page and get topic subscribers
    pass