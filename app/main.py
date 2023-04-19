from fastapi import FastAPI
from app.api import router
from app.core.database import create_db
from app.core.config import settings
from app.utils.celery_utils import create_celery


def create_application() -> FastAPI:
    application = FastAPI(title=settings.PROJECT_NAME)
    application.include_router(router)
    application.add_event_handler("startup", create_db)
    application.celery_app = create_celery()
    # application.add_event_handler("startup", create_redis_pool)
    # application.add_event_handler("shutdown", close_redis_pool)
    return application


app = create_application()
celery = app.celery_app

