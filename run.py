import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.handlers import router
from app.database import create_tables
from binance_cl import binance_client  # Импорт функций создания и закрытия клиента
from app.utils import close_all_orders_and_positions, handle_socket_messages, monitor_take_profits, get_or_ask, init_token
# Настройка логгирования
logging.basicConfig(level=logging.INFO)

API_KEY = None
SECRET_KEY = None
TOKEN = None
USER_ID = None

# Функция для чтения данных из файла или запроса у пользователя

# Получение данных
TOKEN = get_or_ask('telegram_token', 'Введіть токен телеграм бота: ')
API_KEY = get_or_ask('binance_api_key', 'Введіть API KEY Binance: ')
SECRET_KEY = get_or_ask('binance_secret_key', 'Введіть SECRET KEY Binance: ')

print(f'Успішно створено користувача:\nTOKEN: {TOKEN}')
init_token(TOKEN)




bot = Bot(token=TOKEN)
dispatcher = Dispatcher()

async def on_startup_func():
    print("Запуск on_startup...")
    await create_tables()
    await binance_client.create_client(API_KEY, SECRET_KEY)  # Создаём клиента Binance
    logging.info('База данных успешно настроена')
    asyncio.create_task(monitor_take_profits(binance_client.client))

async def main() -> None:
    dispatcher.include_router(router)
    await on_startup_func()
    logging.info("Бот запускается...")
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Внезапная ошибка: {str(e)}")