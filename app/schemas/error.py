from typing import Optional
from pydantic import BaseModel


class AlertMessage(BaseModel):
    criticalityLevel: str
    section: str
    operation: str
    errorCode: int
    errorName: str
    operationStatus: str
    operationCodeIFB: str
    operationCodeABS: str
