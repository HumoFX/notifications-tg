
from fastapi import APIRouter

from app.api.v1.push import router as push_router
from app.api.v1.sms_info import router as sms_router
from app.api.v1.webhook import router as webhook_router

router = APIRouter(prefix="/v1")
router.include_router(push_router)
router.include_router(sms_router)
router.include_router(webhook_router)
