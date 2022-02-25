from fastapi import APIRouter

from app.models.users import User, UserCustomer
from app.schemas.notification import Notification
from app.schemas.reponse import ResponseBody
from app.core.config import BotNotify, settings

router = APIRouter(prefix="/notification", tags=["notification"])
bot = BotNotify()


@router.post("/", response_model=ResponseBody, status_code=201)
async def create_task(notification: Notification):
    customer = await UserCustomer.get(notification.customerId)
    if customer:
        # message = await bot.send_message(customer.user_id, notification.body)
        message = bot.sendMessage(customer.user_id, notification.body)
        if message.get("ok"):
            return ResponseBody(status=0, data={"message": "success"})
        elif message.get("error_code") == 404:
            return ResponseBody(status=1000, errorMessage="User not found")
        else:
            return ResponseBody(status=1001, errorMessage="Failed to send message")
    else:
        return ResponseBody(status=2000, errorMessage="Customer not found")
