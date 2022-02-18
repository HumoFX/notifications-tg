
from fastapi import APIRouter

from app.api.v1.push import router as push_router

router = APIRouter(prefix="/v1")
router.include_router(push_router)