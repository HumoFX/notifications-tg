from typing import Optional
from pydantic import BaseModel


class Notification(BaseModel):
    title: Optional[str]
    body: str
    fcmToken: Optional[str]
    applicationId: Optional[str]
    actionType: Optional[str]
    customerId: Optional[int]
    uuid: Optional[str]
    topicName: Optional[str]
