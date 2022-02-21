from fastapi import APIRouter

from app.core import redis
from app.core.models import User
from app.schemas.notification import Notification
from app.schemas.reponse import ResponseBody
from app.core.config import TelegramBot, settings

router = APIRouter(prefix="/notification", tags=["notification"])


@router.post("/", response_model=ResponseBody, status_code=201)
async def create_task(notification: Notification):
    # filter user from User model by notification.customerId in data field
    user = await User.get(notification.customerId).first()

    telegram_bot = TelegramBot()
    print(settings.POSTGRES_URI)
    print(notification)
    response = ResponseBody(status=0, data={"message": "success"})
    return response


# @router.get("/{task_id}/")
# async def get_task(task_id: str):
#     job = ArqJob(task_id, redis.pool)
#     return await job.info()
