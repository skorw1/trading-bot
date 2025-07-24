from binance import AsyncClient, Client
import asyncio
import ta
from datetime import datetime
from app.database import get_currency_pair
import time
from binance import BinanceSocketManager
import pytz
import math
import aiohttp
import asyncio
from aiogram import Bot
from decimal import Decimal, ROUND_DOWN
from binance_cl import binance_client
import sys
import os
import json
import pandas as pd

CONFIG_FILE = 'config.json'

def get_config_path():
    # Путь к файлу config.json рядом с exe
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
    return os.path.join(os.path.dirname(__file__), CONFIG_FILE)

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data: dict):
    path = get_config_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_or_ask(key: str, prompt: str) -> str:
    config = load_config()
    if key not in config or not config[key].strip():
        config[key] = input(prompt).strip()
        save_config(config)
    return config[key]


ALLOWED_USER_ID = get_or_ask('telegram_user_id', 'Введіть id телеграм користувача: ')
bot = None
TOKEN = None

def init_token(token: str):
    global TOKEN, bot
    TOKEN = token
    bot = Bot(token=TOKEN)


tracking_orders = {} # для отслеживания ордеров
tracking_orders_for_limit = {} # для отслеживания ордеров в случае, если выполняется лимитка на усреднение

async def close_all_orders_and_positions(symbol: str):
    """
    Асинхронно закрывает все открытые ордера и позиции для указанной торговой пары.
    """
    client = binance_client.client
    try:
        # Закрытие всех открытых ордеров
        open_orders = await client.futures_get_open_orders(symbol=symbol)
        if open_orders:
            print(f"Закрытие открытых ордеров для {symbol}...")
            for order in open_orders:
                try:
                    order_id = order['orderId']
                    await client.futures_cancel_order(symbol=symbol, orderId=order_id)
                    print(f"Ордер ID {order_id} отменён.")
                except Exception as e:
                    print(f"Ошибка при отмене ордера {order}: {e} ({type(e)})")
        else:
            print(f"Нет открытых ордеров для {symbol}.")

        has_positions = False

        # Получение информации о позициях
        try:
            positions = await client.futures_position_information(symbol=symbol)
            print(f"Полученные позиции: {positions}")
        except Exception as e:
            print(f"Ошибка при получении позиций: {e} ({type(e)})")
            return

        # Закрытие всех непустых позиций
        for position in positions:
            try:
                position_amt = float(position.get('positionAmt', 0))
                print(f"Обнаружена позиция: {position_amt} для {symbol}")

                if position_amt != 0:
                    has_positions = True
                    position_side = 'SELL' if position_amt > 0 else 'BUY'

                    await client.futures_create_order(
                        symbol=symbol,
                        side=position_side,
                        type="MARKET",
                        quantity=abs(position_amt),
                        reduceOnly=True
                    )
                    print(f"Позиция для {symbol} закрыта.")

                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Позиція для {symbol} закрита')
                    except Exception as e:
                        print(f'Ошибка при отправке сообщения: {e} ({type(e)})')

            except Exception as e:
                print(f"Ошибка при обработке позиции: {position}, ошибка: {e} ({type(e)})")

    except Exception as e:
        try:
            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при закритті позиції / ордера: {e}')
        except Exception as e:
            print(f'Ошибка при отправке сообщения об ошибке: {e} ({type(e)})')
        print(f"Произошла ошибка: {e} ({type(e)})")

async def handle_socket_messages(msg, client):
    """
    Обрабатывает сообщения из WebSocket.
    """
    print(msg)
    if msg['e'] == 'ORDER_TRADE_UPDATE':  # Событие об ордере
        msg = msg['o']
        order_status = msg['X']  # Статус ордера (например, FILLED)
        order_type = msg['ot']    # Тип ордера (например, TAKE_PROFIT_MARKET)
        executed_qty = msg['l']  # Исполненное количество
        executed_price = msg['L']  # Цена исполнения
        symbol = msg['s']
        order_id = msg['i']  # ID ордера

        if order_status == 'FILLED' and order_type == 'LIMIT':
            # Если это лимитный ордер, проверяем в tracking_orders
            if order_id in tracking_orders:
                tracking_data = tracking_orders[order_id]
                market_order_price = tracking_data['market_order_price']
                market_quantity = tracking_data['market_quantity']
                limit_order_price = tracking_data['limit_order_price']
                limit_quantity = tracking_data['limit_quantity']
                take_profit1 = tracking_data['take_profit1']
                take_profit_side = tracking_data['take_profit_side']
                tick_size = tracking_data['tick_size']
                take_profit_id = tracking_data['take_profit_id']
                step_size = await get_step_size(symbol, client)
                stop_loss_id = tracking_data['stop_loss_id']
                print(tracking_orders[order_id])
                print(f"Лимитный ордер исполнен для {symbol}: Цена {executed_price}, Количество {executed_qty}")
                # Создание ордера тейк-профита
                average_price = (market_order_price * market_quantity + limit_order_price * limit_quantity) / (market_quantity + limit_quantity)
                if take_profit_side == 'BUY':
                    tp_price = round_to_tick_size(average_price * (1-take_profit1/100), tick_size)
                elif take_profit_side == 'SELL':
                    tp_price = round_to_tick_size(average_price * (1+take_profit1/100), tick_size)
                print(f"Тейк-профит на цену {tp_price}")
                try:
                    await client.futures_cancel_order(symbol=symbol, orderId=take_profit_id)
                    del tracking_orders[take_profit_id]
                    del tracking_orders[stop_loss_id]

                    print('limit tracking orders:', tracking_orders)
                    print('логика1 новой лимитки', symbol, take_profit_side, tp_price, limit_quantity+market_quantity)
                    quantity_total = round_to_step_size(limit_quantity+market_quantity, step_size)
                    order_tp_data = await client.futures_create_order(
                        symbol=symbol,
                        side=take_profit_side,  # Используем сторону тейк-профита
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=tp_price,
                        quantity=quantity_total,
                        timeInForce='GTC'
                    )
                    tracking_orders_for_limit[order_tp_data['orderId']] = {
                        'stop_loss_id': stop_loss_id
                    }
                    print(f"Тейк-профит установлен на уровне {tp_price}")
                except Exception as e:
                    print(f"Ошибка при установке тейк-профита: {e}")
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка: {e} при виставлені лімітного ордеру для {symbol}, зі стороною {take_profit_side}, по ціні {tp_price}, та з кількістью {quantity_total}')
                    except Exception as e:
                        print('Exception on await send message:', e)
                # Удаляем лимитный ордер из tracking_orders после исполнения
                del tracking_orders[order_id]
            else:
                print('Лимитный ордер выполнен, но его нету в tracking_orders')
        elif order_status == 'FILLED' and order_type == 'TAKE_PROFIT_MARKET':
            try:
                if order_id in tracking_orders:
                    print('Вывожу информацию про весь tracking_orders:')
                    tracking_data = tracking_orders[order_id]
                    market_order_price = tracking_data['market_order_price']
                    market_quantity = tracking_data['market_quantity']
                    limit_order_price = tracking_data['limit_order_price']
                    limit_quantity = tracking_data['limit_quantity']
                    take_profit1 = tracking_data['take_profit1']
                    take_profit_side = tracking_data['take_profit_side']
                    take_profit_quantity1 = tracking_data['take_profit_quantity1']
                    take_profit_quantity2 = tracking_data['take_profit_quantity2']
                    take_profit_quantity3 = tracking_data['take_profit_quantity3']
                    tick_size = tracking_data['tick_size']
                    take_profit_id = tracking_data['take_profit_id']
                    step_size = await get_step_size(symbol, client)
                    counter = tracking_data['counter']
                    take_profit_price1 = tracking_data['take_profit_price1']
                    take_profit_price2 = tracking_data['take_profit_price2']
                    take_profit_price3 = tracking_data['take_profit_price3']
                    stop_loss_id = tracking_data['stop_loss_id']
                    print('counter:', counter, str(tracking_data))
                    if counter == 1:
                        print('inside counter 1')
                        new_take_profit = await client.futures_create_order(
                            symbol=symbol,
                            side=take_profit_side,  # Используем сторону тейк-профита
                            type='TAKE_PROFIT_MARKET',
                            stopPrice=take_profit_price2,
                            quantity=take_profit_quantity2,
                            timeInForce='GTC'
                        )
                        print('после тейк профит 2 выставления:', new_take_profit)
                        res = await client.futures_cancel_order(symbol=symbol, orderId=stop_loss_id)
                        print('после отмены стопа:', res)
                        sl = await client.futures_create_order(
                            symbol=symbol,
                            side=take_profit_side,
                            type='STOP_MARKET',
                            stopPrice=market_order_price,
                            quantity=take_profit_quantity1
                        )
                        print('выставлен новый стоп', sl)
                        tracking_orders[new_take_profit['orderId']] = tracking_orders[order_id].copy()
                        print('после копирования в tracking orders нового тейка')
                        tracking_orders[new_take_profit['orderId']]['stop_loss_id'] = sl['orderId']
                        print('после присвоения нового стоп лосса для предыдущего тейка в tracking orders')
                        tracking_orders[sl['orderId']] = {
                            'take_profit_id': order_id
                        }
                        print('после создания новой записи в tracking для стопа')
                        tracking_orders[new_take_profit['orderId']]['counter'] += 1
                        print('После увеличения counter:', tracking_orders[new_take_profit['orderId']]['counter'])

                        del tracking_orders[order_id]
                        print(f'перед удалением стопа с id {stop_loss_id} из tracking orders:', tracking_orders)
                        del tracking_orders[stop_loss_id]
                        print('после удаления стопа из tracking orders')
                        try:
                            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Виконався тейк профіт для {symbol}. Встановлено новий тейк на 30%, і стоп лосс"')
                        except Exception as e:
                            print(f'Exception on await send message: {e}')
                    elif counter == 2:
                        print('inside counter 2')
                        new_take_profit = await client.futures_create_order(
                            symbol=symbol,
                            side=take_profit_side,  # Используем сторону тейк-профита
                            type='TAKE_PROFIT_MARKET',
                            stopPrice=take_profit_price3,
                            quantity=take_profit_quantity3,
                            timeInForce='GTC'
                        )
                        await client.futures_cancel_order(symbol=symbol, orderId=stop_loss_id)
                        sl = await client.futures_create_order(
                            symbol=symbol,
                            side=take_profit_side,
                            type='STOP_MARKET',
                            stopPrice=take_profit_price1,
                            quantity=take_profit_quantity3
                        )
                        tracking_orders[new_take_profit['orderId']] = tracking_orders[order_id]
                        tracking_orders[new_take_profit['orderId']]['stop_loss_id'] = sl['orderId']
                        tracking_orders[sl['orderId']] = {
                            'take_profit_id': order_id
                        }
                        tracking_orders[new_take_profit['orderId']]['counter'] += 1
                        print('После увеличения counter:', tracking_orders[new_take_profit['orderId']]['counter'])
                        del tracking_orders[order_id] # Удаляем из отслеживания уже исполнившиеся ордера
                        del tracking_orders[stop_loss_id] # Удаляем из отслеживания уже исполнившиеся ордера
                        try:
                            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Виконався тейк профіт для {symbol}. Встановлено новий тейк на 20%, і стоп лосс"')
                        except Exception as e:
                            print(f'Exception on await send message: {e}')
                    elif counter == 3:
                        await close_all_orders_and_positions(symbol) # закрываем все позиции и ордера после выполнения третьего тейка
                        del tracking_orders[order_id]
                        del tracking_orders[stop_loss_id]
                        try:
                            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Виконався тейк профіт для {symbol}. Видалені усі ордери по торговій парі."')
                        except Exception as e:
                            print(f'Exception on await send message: {e}')
                    else:
                        print('error in counter!!!')
                elif order_id in tracking_orders_for_limit:
                    data = tracking_orders_for_limit[order_id]

                    stop_loss_id = data['stop_loss_id']
                    try:
                        await client.futures_cancel_order(symbol=symbol, orderId=stop_loss_id)
                        try:
                            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Успішно видалено стоп-лосс ордер після виконання тейк профіту (ліміт усереднення)')
                        except Exception as ex:
                            print(f'Exception on await send message: {ex}')
                    except Exception as e:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при видаленні стоп лоссу після виконання тейк профіт ордеру (ліміт усереднення): {e}')
                    del tracking_orders_for_limit[order_id]
                else:
                    print(f'order id {order_id} does not exist in any tracking orders id.')
            except Exception as e:
                print('Exception', e)
                try:
                    await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Виконався стоп лосс для {symbol}. Видалено усі ордери по торговій парі"')
                except Exception as exep:
                    print(f'Exception on await send message: {exep}')
        elif order_status == 'FILLED' and order_type == 'STOP_MARKET':
            print(f"{order_type} исполнен для {symbol}: Количество {executed_qty}, Цена {executed_price}")
            await close_all_orders_and_positions(symbol)
            take_profit_id = tracking_orders[order_id]['take_profit_id']
            del tracking_orders[order_id]
            del tracking_orders[take_profit_id]
            try:
                await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Виконався стоп лосс для {symbol}. Видалено усі ордери по торговій парі"')
            except Exception as e:
                print(f'Exception on await send message: {e}')

async def monitor_take_profits(client):
    """
    Отслеживает исполнение тейк-профитов через WebSocket.
    """
    bsm = BinanceSocketManager(client)
    socket = bsm.futures_user_socket()

    async with socket as stream:
        print("WebSocket запущен. Ожидание событий...")
        try:
            while True:
                msg = await stream.recv()
                await handle_socket_messages(msg, client)
        except asyncio.CancelledError:
            print("Мониторинг тейк-профитов был остановлен.")
        except Exception as e:
            print(f"Ошибка в WebSocket: {e}")
            # здесь стоит переподключить WebSocket, если ошибка повторяется
            await asyncio.sleep(5)
            await monitor_take_profits(client)  # Попробовать переподключение


async def get_open_orders_by_pair(client: AsyncClient, symbol: str):
    try:
        # Получение всех открытых ордеров для указанной валютной пары
        open_orders = await client.futures_get_open_orders(symbol=symbol)
        return open_orders
    except Exception as e:
        print(f"Ошибка при получении открытых ордеров: {e}")
        return []
async def get_data_local(symbol, interval, limit):
    url = f'http://localhost:8000/data?symbol={symbol}&interval={interval}'
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    json_data = await response.json()
                    data = json_data.get('data', [])
                    if not data:
                        return None
                    data = data[-limit:] if limit and len(data) >= limit else data
                    open_prices = [float(c[1]) for c in data]
                    high_prices = [float(c[2]) for c in data]
                    low_prices = [float(c[3]) for c in data]
                    close_prices = [float(c[4]) for c in data]
                    return open_prices, high_prices, low_prices, close_prices
                else:
                    return None
        except Exception:
            return None

async def get_data(symbol, interval, limit):
    url = f'https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    # Проверяем на наличие ошибок в ответе
    if isinstance(data, dict) and "code" in data:
        raise ValueError(f"Ошибка API Binance: {data}")

    # Проверяем корректность формата данных
    if not data or not all(isinstance(row, list) and len(row) >= 5 for row in data):
        raise ValueError("Некорректный формат данных, полученных от API")

    # Извлекаем необходимые данные
    open_prices = [float(each[1]) for each in data]  # Открытие
    high_prices = [float(each[2]) for each in data]  # Высокий
    low_prices = [float(each[3]) for each in data]   # Низкий
    close_prices = [float(each[4]) for each in data] # Закрытие

    # Логируем первые 5 значений для диагностики

    return open_prices, high_prices, low_prices, close_prices
async def get_data_with_fallback(symbol, interval, limit):
    # Пробуем сначала локальный сервер
    local_result = await get_data_local(symbol, interval, limit)
    if local_result is not None:
        return local_result
    # Если локальный сервер не ответил — вызываем оригинальную функцию напрямую
    print(f"Локальный сервер не ответил, получаем данные с Binance API для {symbol} {interval}")
    return await get_data(symbol, interval, limit)

# Функция для получения шага размера (stepSize) для символа
async def get_step_size(symbol, client):
    info = await client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            return float(s['filters'][2]['stepSize'])  # Шаг для размера актива

# Округление количества актива до допустимого stepSize
def round_to_step_size(quantity, step_size):
    return round(math.floor(quantity / step_size) * step_size, len(str(step_size).split('.')[1]))

# Обновленная функция для расчета количества актива с учетом stepSize
async def calculate_qn(dep, leverage, symb, client):
    step_size = await get_step_size(symb, client)  # Получаем stepSize для символа
    current_price = await get_current_price(symb, client)
    usdt_amount = dep * leverage
    quantity = usdt_amount / current_price
    rounded_quantity = round_to_step_size(quantity, step_size)  # Округляем количество
    print(f"Количество для {symb}: {rounded_quantity}")
    print(rounded_quantity)
    return rounded_quantity, current_price

async def calculate_limit_qn(dep, limit_x, limit_percent, symb, client):
    step_size = await get_step_size(symb, client)  # Получаем stepSize для символа
    current_price = await get_current_price(symb, client)
    current_price = current_price / 100 * (100-limit_percent)
    usdt_amount = dep * limit_x
    quantity = usdt_amount / current_price
    rounded_quantity = round_to_step_size(quantity, step_size)  # Округляем количество
    print(f"Количество для {symb}: {rounded_quantity}")
    print(rounded_quantity)
    return rounded_quantity




# Асинхронная функция получения текущей цены актива
async def get_current_price(symbol, client: AsyncClient):


    ticker = await client.futures_symbol_ticker(symbol=symbol)
    print(ticker)
    return float(ticker['price'])


# Расчет количества актива для ордера
def calculate_quantity(dep, price, leverage):
    usdt_amount = dep * leverage  # Депозит умножаем на кредитное плечо
    quantity = usdt_amount / price  # Количество актива на основе цены
    return quantity



# Функция для получения тик-шага (tickSize) для символа
async def get_tick_size(symbol, client):

    info = await client.futures_exchange_info()
    symbols = info.get('symbols', [])
    # Проверяем, есть ли символ в списке
    for s in symbols:
        if s.get('symbol') == symbol:
            filters = s.get('filters', [])
            if not filters or len(filters) < 1:
                print(f"Отсутствуют фильтры для символа {symbol}. Полные данные: {s}")
                return None
            tick_size = filters[0].get('tickSize')
            if tick_size is None:
                print(f"Ключ 'tickSize' отсутствует в фильтре: {filters[0]}")
                return None
            # Преобразуем tick_size из научной нотации в float и проверяем точность
            tick_size = float(f"{float(tick_size):.10g}")  # Ограничиваем до 10 значащих цифр
            print(f"Tick size для {symbol}: {tick_size}")
            return tick_size
    # Если символ не найден
    print(f"Символ {symbol} не найден в данных биржи. Ответ Binance: {info}")
    return None



# Округление цены до допустимого tickSize
def round_to_tick_size(price, tick_size):
    try:
        # Преобразуем цену и tick_size в тип Decimal для точных вычислений
        price = Decimal(str(price))
        tick_size = Decimal(str(tick_size))

        # Рассчитываем количество знаков после запятой для tick_size
        tick_size_str = f"{tick_size:.20f}".rstrip('0')
        decimal_places = len(tick_size_str.split('.')[1]) if '.' in tick_size_str else 0
        print(f"tick size: {tick_size}, decimal places: {decimal_places}")

        # Вычисляем округленную цену с учетом точности
        rounded_price = (price // tick_size) * tick_size

        # Округляем до нужной точности
        rounded_price = rounded_price.quantize(Decimal(f'1e-{decimal_places}'), rounding=ROUND_DOWN)
        print(f"rounded price: {rounded_price}")

        return float(rounded_price)
    except Exception as e:
        print(f"Ошибка в функции round_to_tick_size: {e}")
        return None



async def close_position(symbol, side, client):
    try:
        await client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',  # Рыночный ордер для немедленного закрытия
            quantity=await get_current_position_quantity(symbol, client),  # Текущее количество
            reduceOnly=True  # Закрыть только открытую позицию
        )
        print(f"Позиция для {symbol} успешно закрыта.")
    except Exception as e:
        print(f"Ошибка при закрытии позиции для {symbol}: {e}")

async def get_current_position_quantity(symbol, client):
    positions = await client.futures_account()
    for position in positions['positions']:
        if position['symbol'] == symbol:
            return abs(float(position['positionAmt']))  # Возвращаем абсолютное количество


# Обновленная функция для размещения ордера с корректным округлением цен

async def check_time(client):
    # Получение серверного времени
    server_time_data = await client.get_server_time()
    server_time = server_time_data['serverTime']

    # Локальное время в миллисекундах
    local_time = int(time.time() * 1000)

    # Расчёт разницы
    time_diff = server_time - local_time

    print(f"Server time: {server_time}, Local time: {local_time}")
    print(f"Time difference: {time_diff} ms")

    if abs(time_diff) > 1000:
        print("Warning: Time difference is too large!")

async def place_order(order_type, symbol, dep, leverage, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x, client):
    # Расчет количества актива
    await check_time(client)
    quantity, order_price = await calculate_qn(dep, leverage, symbol, client)
    step_size = await get_step_size(symbol, client)
    take_limit_quantity1 = round_to_step_size(quantity / 100 * 50, step_size)
    take_limit_quantity2 = round_to_step_size(quantity / 100 * 30, step_size)
    take_limit_quantity3 = round_to_step_size(quantity / 100 * 20, step_size)
    try:
        print('перед вычислением tick_size')
        tick_size = await get_tick_size(symbol, client)  # Получаем tickSize для символа
        print(f'после tick size, - {tick_size}')

        if order_type == 'BUY':
            # Открытие длинной позиции (лонг)
            order = await client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',     # Рыночный ордер
                quantity=quantity
            )
            print(order, 'Открыта лонг позиция')
            print(f'Після відкриття ордеру, прайс на пару: {order_price}')
            await asyncio.sleep(0.5)

            if take_profit1:
                try:
                    print('перед вычислением tp_price')
                    tp_price1 = round_to_tick_size(order_price * (1 + take_profit1 / 100), tick_size)
                    tp_price2 = round_to_tick_size(order_price * (1 + take_profit2 / 100), tick_size)
                    tp_price3 = round_to_tick_size(order_price * (1 + take_profit3 / 100), tick_size)
                    print(tp_price1, 'tp_price long take')
                    tp = await client.futures_create_order(
                        symbol=symbol,
                        side='SELL',      # Для лонга тейк-профит будет sell
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=tp_price1,  # Рассчитанная цена тейк-профита
                        quantity=take_limit_quantity1,
                        timeInForce='GTC'
                    )
                    print(f"Тейк-профит установлен на уровне {tp_price1}")
                except Exception as e:
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при установленні тейку (лонг): "{e}"')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    await close_position(symbol, 'SELL', client)
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ордер успішно закрито')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    return

            if stop_loss:
                print('перед вычислением sl_price')
                sl_price = round_to_tick_size(order_price * (1 - stop_loss / 100), tick_size)
                print(sl_price, 'sl_price long stop loss')
                try:
                    sl = await client.futures_create_order(
                        symbol=symbol,
                        side='SELL',      # Для лонга стоп-лосс будет sell
                        type='STOP_MARKET',
                        stopPrice=sl_price,  # Рассчитанная цена стоп-лосса
                        quantity=quantity,
                        timeInForce='GTC'
                    )
                    print(f"Стоп-лосс установлен на уровне {sl_price}")
                except Exception as e:
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при установленні стоп-лоссу (лонг): {e}')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    await close_position(symbol, 'SELL', client)
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ордер успішно закрито')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    return

            #открытие лимит ордера

            try:
                # Рассчитываем цену лимитного ордера
                limit_qn = await calculate_limit_qn(dep*leverage, limit_x, limit_percent, symbol, client)
                current_price = await get_current_price(symbol, client)
                limit_price = round_to_tick_size(current_price * (1 - limit_percent / 100), tick_size)
                print(f"limig_qn: {limit_qn}, dep: {dep}, limix x: {limit_x}, limit_percent: {limit_percent}, current price: {current_price}")
                print(f"Лимитная цена для ордера: {limit_price}")
                # Создаем лимитный ордер
                limit_order = await client.futures_create_order(
                    symbol=symbol,
                    side='BUY',  # Покупка по лимитной цене
                    type='LIMIT',  # Лимитный ордер
                    price=limit_price,  # Рассчитанная цена лимитного ордера
                    quantity=limit_qn,  # Рассчитанное количество актива
                    timeInForce='GTC'  # Ордер будет активен до отмены (Good Till Cancelled)
                )
                print(f"Лимитный ордер успешно создан: {limit_order}")
                limit_order_id = limit_order['orderId']  # Получаем ID лимитного ордера
                tracking_data = {
                    'market_order_price': order_price,
                    'market_quantity': quantity,
                    'take_profit_price1': tp_price1,
                    'take_profit_price2': tp_price2,
                    'take_profit_price3': tp_price3,
                    'take_profit_quantity1': take_limit_quantity1,
                    'take_profit_quantity2': take_limit_quantity2,
                    'take_profit_quantity3': take_limit_quantity3,
                    'limit_order_price': limit_price,
                    'limit_quantity': limit_qn,
                    'take_profit1': take_profit1,
                    'take_profit2': take_profit2,
                    'take_profit3': take_profit3,
                    'tick_size': tick_size,
                    'take_profit_id': tp['orderId'],
                    'take_profit_side': 'SELL',  # Для лонга тейк-профит будет SELL
                    'stop_loss_id': sl['orderId'],
                    'counter': 1
                }
                tracking_data_for_stop = {
                    'take_profit_id': tp['orderId'],
                    'stop_loss_id': sl['orderId']
                }
                tracking_orders[limit_order_id] = tracking_data.copy()
                tracking_orders[tp['orderId']] = tracking_data.copy()
                tracking_orders[sl['orderId']] = tracking_data_for_stop
                print(f"Данные лимитного ордера добавлены в tracking_orders: {tracking_orders[limit_order_id]}")
            except Exception as e:
                print(f"Ошибка при выставлении лимитного ордера: {e}")
                try:
                    await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ошибка при выставлении лимитного ордера: {e}')
                except Exception as e:
                    print(f'Exception on await send message: {e}')

        elif order_type == 'SELL':
            # Открытие короткой позиции (шорт)
            order = await client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',     # Рыночный ордер
                quantity=quantity
            )
            print(order, 'Открыта шорт позиция')

            await asyncio.sleep(0.5)

            # Получение текущей цены
            order_price = await get_current_price(symbol, client)
            print('get_current_price - корректно')

            if take_profit1:
                print('перед вычислением tp_price')
                tp_price1 = round_to_tick_size(order_price * (1 - take_profit1 / 100), tick_size)
                tp_price2 = round_to_tick_size(order_price * (1 - take_profit2 / 100), tick_size)
                tp_price3 = round_to_tick_size(order_price * (1 - take_profit3 / 100), tick_size)
                print(tp_price1, 'tp_price short take')

                try:
                    tp = await client.futures_create_order(
                        symbol=symbol,
                        side='BUY',       # Для шорта тейк-профит будет buy
                        type='TAKE_PROFIT_MARKET',
                        stopPrice=tp_price1,  # Рассчитанная цена тейк-профита
                        quantity=take_limit_quantity1,
                        timeInForce='GTC'
                    )
                    print(f"Тейк-профит установлен на уровне {tp_price1}")
                except Exception as e:
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при установленні тейку (шорт): {e}')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    await close_position(symbol, 'BUY', client)
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ордер успішно закрито')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    return

            if stop_loss:
                print('перед вычислением sl_price')
                sl_price = round_to_tick_size(order_price * (1 + stop_loss / 100), tick_size)
                print(sl_price, 'sl_price short stop loss')
                try:
                    sl = await client.futures_create_order(
                        symbol=symbol,
                        side='BUY',       # Для шорта стоп-лосс будет buy
                        type='STOP_MARKET',
                        stopPrice=sl_price,  # Рассчитанная цена стоп-лосса
                        quantity=quantity,
                        timeInForce='GTC'
                    )
                    print(f"Стоп-лосс установлен на уровне {sl_price}")
                except Exception as e:
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Помилка при установленні стопу (шорт): {e}')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    await close_position(symbol, 'BUY', client)
                    try:
                        await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ордер успішно закрито')
                    except Exception as e:
                        print(f'Exception on await send message: {e}')
                    return
            try:
                # Рассчитываем цену лимитного ордера
                limit_qn = await calculate_limit_qn(dep*leverage, limit_x, -limit_percent, symbol, client)
                current_price = await get_current_price(symbol, client)
                limit_price = round_to_tick_size(current_price * (1 + limit_percent / 100), tick_size)
                print(f"Лимитная цена для ордера: {limit_price}")
                print(f"limig_qn: {limit_qn}, dep: {dep}, limix x: {limit_x}, limit_percent: {limit_percent}, current price: {current_price}")
                print(f"Лимитная цена для ордера: {limit_price}")

                # Создаем лимитный ордер

                limit_order = await client.futures_create_order(
                    symbol=symbol,
                    side='SELL',  # Покупка по лимитной цене
                    type='LIMIT',  # Лимитный ордер
                    price=limit_price,  # Рассчитанная цена лимитного ордера
                    quantity=limit_qn,  # Рассчитанное количество актива
                    timeInForce='GTC'  # Ордер будет активен до отмены (Good Till Cancelled)
                )

                limit_order_id = limit_order['orderId']
                tracking_data = {
                    'market_order_price': order_price,
                    'market_quantity': quantity,
                    'take_profit_price1': tp_price1,
                    'take_profit_price2': tp_price2,
                    'take_profit_price3': tp_price3,
                    'take_profit_quantity1': take_limit_quantity1,
                    'take_profit_quantity2': take_limit_quantity2,
                    'take_profit_quantity3': take_limit_quantity3,
                    'limit_order_price': limit_price,
                    'limit_quantity': limit_qn,
                    'take_profit1': take_profit1,
                    'take_profit2': take_profit2,
                    'take_profit3': take_profit3,
                    'tick_size': tick_size,
                    'take_profit_id': tp['orderId'],
                    'take_profit_side': 'BUY',
                    'stop_loss_id': sl['orderId'],
                    'counter': 1
                }

                tracking_data_for_stop = {
                    'take_profit_id': tp['orderId'],
                    'stop_loss_id': sl['orderId']
                }

                tracking_orders[limit_order_id] = tracking_data.copy()
                tracking_orders[tp['orderId']] = tracking_data.copy()
                tracking_orders[sl['orderId']] = tracking_data_for_stop
            except Exception as e:
                print(f"Ошибка при выставлении лимитного ордера: {e}")
                try:
                    await bot.send_message(chat_id=ALLOWED_USER_ID, text=f'Ошибка при выставлении лимитного ордера: {e}')
                except Exception as e:
                    print(f'Exception on await send message: {e}')
        try:
            await bot.send_message(chat_id=ALLOWED_USER_ID, text=f"Успішно відкрито {'лонг' if order_type == 'BUY' else 'шорт'} позицію для {symbol}. Кількість: {quantity}. Ціна: {order_price}")
        except Exception as e:
            print(f'Exception on await send message: {e}')


    except Exception as e:
        print('Ошибка при создании ордера', e)




async def start_trading(message, symbol, strategy_name):

    # Получение данных из базы данных
    print(symbol, strategy_name)
    pair_info = await get_currency_pair('database.db', symbol, strategy_name)
    if not pair_info:
        try:
            await message.answer("Пара не знайдена в базі даних.")
        except Exception as e:
            print(f'Exception on await send message: {e}')
        return

    updating = pair_info[3]
    timeframe = pair_info[4]
    dep = pair_info[5]
    leverage = pair_info[6]
    rsi_long = pair_info[7]
    prev_rsi_long = pair_info[8]
    rsi_short = pair_info[9]
    prev_rsi_short = pair_info[10]
    rsi_period = pair_info[11]
    rsi_type = pair_info[12]
    stop_loss = pair_info[13]
    take_profit1 = pair_info[14]
    take_profit2 = pair_info[15]
    take_profit3 = pair_info[16]
    limit_percent = pair_info[17]
    limit_x = pair_info[18]

    await asyncio.sleep(0.5)

    if (symbol, strategy_name) not in tasks:
        task = asyncio.create_task(trade(symbol, updating, timeframe, dep, leverage, rsi_long, prev_rsi_long, rsi_short, prev_rsi_short, rsi_period, rsi_type, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x))
        tasks[(symbol, strategy_name)] = task
        try:
            await message.answer(f"Запущена торговля для {symbol}.")
        except Exception as e:
            print(f'Exception on await send message: {e}')
    else:
        try:
            await message.answer(f"Торговля для {symbol} уже запущена.")
        except Exception as e:
            print(f'Exception on await send message: {e}')

async def stop_trading(message, symbol, strategy_name):
    if (symbol, strategy_name) in tasks:
        tasks[(symbol, strategy_name)].cancel()
        del tasks[(symbol, strategy_name)]
        print(f'остановка торговли для {symbol}')
        try:
            await message.answer(f"Остановка торговли для {symbol}.")
        except Exception as e:
            print(f'Exception on await send message: {e}')
    else:
        try:
            await message.answer(f"Торговля для {symbol} не была запущена.")
        except Exception as e:
            print(f'Exception on await send message: {e}')

async def trade(symbol, updating, timeframe, dep, leverage, rsi_long, prev_rsi_long, rsi_short, prev_rsi_short, rsi_period, rsi_type, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x):
    client = binance_client.client
    position = None
    prev_rsi = None
    print(f'Запуск торговли для {symbol}. Обновление RSI происходит каждые {updating} секунд.\n')

    valid_rsi_types = {
        'open': 0,
        'high': 1,
        'low': 2,
        'close': 3,
        'hl2': 4,
        'hlc3': 5,
        'ohlc4': 6,
        'hlcc4': 7
    }

    while True:
        try:
            open_prices, high_prices, low_prices, close_prices = await get_data_with_fallback(symbol, timeframe, limit=200)

            if rsi_type not in valid_rsi_types:
                print(f"Недопустимый тип данных для RSI: {rsi_type}. Используйте один из: {', '.join(valid_rsi_types.keys())}")
                await asyncio.sleep(updating)
                break

            if rsi_type == 'open':
                rsi_data = open_prices
            elif rsi_type == 'high':
                rsi_data = high_prices
            elif rsi_type == 'low':
                rsi_data = low_prices
            elif rsi_type == 'close':
                rsi_data = close_prices
            elif rsi_type == 'hl2':
                rsi_data = [(high + low) / 2 for high, low in zip(high_prices, low_prices)]
            elif rsi_type == 'hlc3':
                rsi_data = [(high + low + close) / 3 for high, low, close in zip(high_prices, low_prices, close_prices)]
            elif rsi_type == 'ohlc4':
                rsi_data = [(open + high + low + close) / 4 for open, high, low, close in zip(open_prices, high_prices, low_prices, close_prices)]
            elif rsi_type == 'hlcc4':
                rsi_data = [(high + low + close + close) / 4 for high, low, close in zip(high_prices, low_prices, close_prices)]
            try:
                rsi_data = [float(value) for value in rsi_data]
            except ValueError as e:
                print(f"Ошибка преобразования данных в float: {e}")
                continue
            df = pd.DataFrame({rsi_type: rsi_data})
            df['rsi'] = ta.momentum.RSIIndicator(df[rsi_type], window=rsi_period).rsi()

            rsi = df['rsi'].iloc[-1]
            kiev_time = datetime.now()

            print(f'[{symbol}] RSI: {rsi}')
            if position is None:
                if prev_rsi is not None:
                    if rsi > rsi_long and prev_rsi < prev_rsi_long:
                        print(f"[{symbol}] time - {kiev_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        await place_order('BUY', symbol, dep, leverage, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x, client)
                        position = 'LONG'

                    elif rsi < rsi_short and prev_rsi > prev_rsi_short:
                        print(f"[{symbol}] RSI: {rsi}, time - {kiev_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        await place_order('SELL', symbol, dep, leverage, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x, client)
                        position = 'SHORT'

            elif position == 'LONG':
                if rsi < rsi_short and prev_rsi > prev_rsi_short:
                    print(f"[{symbol}] time - {kiev_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    await place_order('SELL', symbol, dep, leverage, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x, client)
                    position = 'SHORT'

            elif position == 'SHORT':
                if rsi > rsi_long and prev_rsi < prev_rsi_long:
                    print(f"[{symbol}] time - {kiev_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    await place_order('BUY', symbol, dep, leverage, stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x, client)
                    position = 'LONG'

            prev_rsi = rsi
            await asyncio.sleep(updating)

        except Exception as e:
            print(f"Ошибка в процессе торговли: {e}")
            await asyncio.sleep(updating)
# Словарь для хранения задач торговли
tasks = {}

