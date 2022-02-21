from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# custom response class with data, errorMessage and status
class ResponseBody(BaseModel):
    data: dict = {}
    errorMessage: Optional[str] = ""
    status: int
