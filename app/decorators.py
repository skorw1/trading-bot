from aiogram.types import Message
from functools import wraps
from app.utils import get_or_ask

ALLOWED_USER_ID = get_or_ask('telegram_user_id', 'Введіть id телеграм користувача: ')


# Здесь нужно вставить реальный ID

def check_user(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):

        if message.from_user.id != int(ALLOWED_USER_ID):
            await message.answer("Вам не дозволено виконувати цю команду.")
            return
        return await func(message, *args, **kwargs)
    return wrapper