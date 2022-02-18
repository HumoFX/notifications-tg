from fastapi import APIRouter

from app.core import redis
from app.schemas.notification import Notification
from app.schemas.reponse import ResponseBody

router = APIRouter(prefix="/notification", tags=["notification"])


@router.post("/", response_model=Notification, status_code=201)
async def create_task(message: str):
    try:
        job = ArqJob(message, redis.pool)
        return await job.create()
    # job = await redis.pool.enqueue_job("test_task", message)
    response = ResponseBody(status=0, data={"message": "success"})
    return Response(s)


@router.get("/{task_id}/")
async def get_task(task_id: str):
    job = ArqJob(task_id, redis.pool)
    return await job.info()
