from typing import Optional
from pydantic import BaseModel


class AlertMessage(BaseModel):
    criticalityLevel:  Optional[str]
    section:  Optional[str]
    operation:  Optional[str]
    errorCode:  Optional[int]
    errorName:  Optional[str]
    operationStatus:  Optional[str]
    operationCodeIFB:  Optional[str]
    operationCodeABS:  Optional[str]
