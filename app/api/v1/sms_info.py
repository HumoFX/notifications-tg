import requests
from fastapi import APIRouter

from app.models.users import User, UserCustomer
from app.schemas.sms import SMS
from app.schemas.reponse import ResponseBody
from app.core.config import BotNotify, settings

router = APIRouter(prefix="/sms_info", tags=["sms"])
bot = BotNotify()


@router.get("/check/{customerId}", response_model=ResponseBody, status_code=200)
async def check_auth(customerId: str):
    """
    Check if the user is authenticated in telegram bot
    :param customerId:
    :return:
    """
    customer = await UserCustomer.get(int(customerId))
    if customer is None:
        return ResponseBody(status=2000, errorMessage="Customer not found")
    else:
        return ResponseBody(status=0, data={"message": f"Customer {customerId} is authenticated in telegram bot"})


@router.post("/send", response_model=ResponseBody, status_code=200)
async def send(sms: SMS):
    """
    Send sms to the user
    :param sms:
    :return:
    """
    customer: UserCustomer = await UserCustomer.get(sms.customer_id)
    message = await bot.send_sms_info(text=sms.message, chat_id=customer.user_id)
    if not customer:
        return ResponseBody(status=2000, errorMessage="Customer not found")
    if message is None:
        return ResponseBody(status=1000, errorMessage="Failed to send message")
    if message.get("ok"):
        return ResponseBody(status=0, data={"message": "Message sent successfully"})
    if message.get("error_code") == 404:
        return ResponseBody(status=1000, errorMessage="Failed to send message")
    else:
        return ResponseBody(status=1001, errorMessage="Failed to send message")


