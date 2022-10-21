from typing import Optional
from pydantic import BaseModel


class SMS(BaseModel):
    customerId: int
    message: str
