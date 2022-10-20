from typing import Optional
from pydantic import BaseModel


class SMS(BaseModel):
    customer_id: int
    message: str
