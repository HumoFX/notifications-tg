from typing import Optional
from pydantic import BaseModel


class Notification(BaseModel):
    body: str
    payload: dict
    newsModel: Optional[dict]
    fcmToken: Optional[str]
    applicationId: Optional[str]
    id: Optional[int]
    topic: Optional[str]
    actionType: Optional[str]
    bannerType: Optional[str]
    language: Optional[str]
    customerId: Optional[int]
    url: Optional[str]
    position: Optional[int]
    createdDateTime: Optional[str]
    udid: Optional[str]
