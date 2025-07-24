import asyncio
import logging
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from binance_cl import binance_client
from app.database import *
from app.messages import *
from app.decorators import check_user
from app.utils import start_trading, stop_trading, get_open_orders_by_pair, place_order

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


logging.basicConfig(level=logging.INFO)

router = Router()


@router.message(CommandStart())
@check_user
async def start_handler(message: Message):
    print(message.from_user.id)
    await message.answer(start_message)


@router.message(Command('create_position'))
@check_user
async def add_pair(message: Message):
    client = binance_client.client
    mess = message.text.replace('/create_position ', '').split()
    pair_lst = mess[:-16]  # Оновлено: параметри тепер враховують strategy_name

    #print(pair_lst)
    #print(int(mess[-14]), mess[-13], float(mess[-12]), int(mess[-11]), float(mess[-10]), float(mess[-9]), float(mess[-8]), float(mess[-7]), int(mess[-6]), str(mess[-5]), float(mess[-4]), float(mess[-3]), float(mess[-2]), int(mess[-1]))

    for i in pair_lst:
        try:
            strategy_name = None
            if ':' in i:
                strategy_name = i[i.find(':')+1:]
                i = i[:i.find(':')]
            await client.futures_change_leverage(symbol=i, leverage=int(mess[-13]))
            await asyncio.sleep(0.3)
            await add_currency_pair(
                'database.db',
                i,
                strategy_name,  # Новий параметр
                int(mess[-16]),
                mess[-15],
                float(mess[-14]),
                int(mess[-13]),
                float(mess[-12]),
                float(mess[-11]),
                float(mess[-10]),
                float(mess[-9]),
                int(mess[-8]),
                str(mess[-7]),
                float(mess[-6]),
                float(mess[-5]),
                float(mess[-4]),
                float(mess[-3]),
                float(mess[-2]),
                int(mess[-1])
            )
            try:
                strategy_info = f" зі стратегією {strategy_name}" if strategy_name else ""
                await message.answer(f'Успішно додана валютна пара {i}{strategy_info}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
        except Exception as e:
            try:
                await message.answer(f'Помилка при додаванні валютної пари {i}: {e}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
@router.message(Command('view_position'))
@check_user
async def view_position(message: Message):
    mess = message.text.replace('/view_position ', '').split()
    try:
        for i in mess:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            info = await get_currency_pair('database.db', i, strategy)
            if info is None:
                try:
                    await message.answer('Пари не знайдено у базі даних. Спочатку додайте пару.')
                except Exception as e:
                    print(f'Exception on await send message: {e}')
            else:
                try:
                    await message.answer(
                        f'Пара: {info[1]}\nінтервал в секундах: {info[3]}\nтаймфрейм: {info[4]}\n'
                        f'розмір позиціїї без плеча: {info[5]}\nкредитне плече: {info[6]}\nrsi лонг: {info[7]}\n'
                        f'минуле rsi лонг: {info[8]}\nrsi шорт: {info[9]}\nминуле rsi шорт: {info[10]}\n'
                        f'період rsi: {info[11]}\nтип rsi: {info[12]}\nstop loss: {info[13]}\n'
                        f'take_profit1: {info[14]}\ntake_profit12 {info[15]}\ntake_profit1: {info[16]}\nвідсоток для ліміт-ордеру: {info[17]}\nмножник для ліміту: {info[18]}'
                    )
                except Exception as e:
                    print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка: {e}')
        except Exception as e:
            print(f'Exception on await send message: {e}')


@router.message(Command('set_update_interval'))
@check_user
async def update_interval(message: Message):
    mess = message.text.replace('/set_update_interval ', '').split()
    pairs = mess[:-1]
    try:
        for i in pairs:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_currency_pair_interval('database.db', i, strategy, int(mess[-1]))
            try:
                await message.answer(f'Успішно змінено інтервал у пари {i} на {mess[-1]} секунд')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer('Помилка при зміненні інтервалів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')


@router.message(Command('set_timeframe'))
@check_user
async def set_timeframe(message: Message):
    mess = message.text.replace('/set_timeframe ', '').split()
    pairs = mess[:-1]
    try:
        for i in pairs:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_currency_pair_timeframe('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено таймфрейм у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer('Помилка при зміненні таймфреймів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')


@router.message(Command('set_position_size'))
@check_user
async def set_dep(message: Message):
    mess = message.text.replace('/set_position_size ', '').split()
    pairs = mess[:-1]
    try:
        for i in pairs:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_currency_pair_position_size('database.db', i, strategy, float(mess[-1]))
            try:
                await message.answer(f'Успішно змінено розмір позиції у пари {i} на {mess[-1]} USDT')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer('Помилка при зміненні розміру позицій для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')


@router.message(Command('set_leverage'))
@check_user
async def change_leverage(message: Message):
    client = binance_client.client
    mess = message.text.replace('/set_leverage ', '').split()
    pairs = mess[:-1]
    try:
        for i in pairs:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_currency_pair_leverage('database.db', i, strategy, mess[-1])
            await client.futures_change_leverage(symbol=i, leverage=int(mess[-1]))
            try:
                await message.answer(f'Успішно змінено кредитне плече у пари {i} на {mess[-1]}X')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer('Помилка при зміненні кредитного плеча у однієї із пари')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('start_trade'))
async def start_trade_handler(message: Message):
    symbols = message.text.replace('/start_trade ', '').split()
    strategy = None

    try:
        for symbol in symbols:
            if ':' in symbol:
                strategy = symbol[symbol.find(':')+1:]
                symbol = symbol[:symbol.find(':')]
            await start_trading(message, symbol, strategy)
    except Exception as e:
        print('Помилка при початку трейдингу', e)
        try:
            await message.answer(f'Помилка при початку трейдинга для пари {symbol}, :{e}')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('stop_trade'))
@check_user
async def stop_trade_handler(message: Message):
    symbols = message.text.replace('/stop_trade ', '').split()
    client = binance_client.client
    strategy = None

    try:
        for s in symbols:
            if ':' in s:
                strategy = s[s.find(':')+1:]
                s = s[:s.find(':')]
            info = await get_currency_pair('database.db', s, strategy)
            orders = await get_open_orders_by_pair(client, s)
            # Проверяем, есть ли хотя бы один открытый ордер
            if orders:
                get_side = orders[0]['side']  # 'BUY' или 'SELL' для первого ордера
                if get_side == 'BUY':
                    await place_order('SELL', info[1], info[5], info[6], info[13], info[14], info[15], info[16], info[17], info[18], client)
                elif get_side == 'SELL':
                    await place_order('BUY', info[1], info[5], info[6], info[13], info[14], info[15], info[16], info[17], info[18], client)

            await stop_trading(message, s, strategy)
    except Exception as e:
        try:
            await message.answer(f'Помилка: {e}')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('view_positions'))
@check_user
async def view_positions(message: Message):
    positions = await get_all_currency_pairs()
    send = 'Ось ваші валютні пари:\n'
    for i in positions:
        send += f'{i}\n'
    try:
        await message.answer(send)
    except Exception as e:
        print(f'Exception on await send message: {e}')

@router.message(Command('delete_position'))
@check_user
async def delete_pair(message: Message):
    mess = message.text.replace('/delete_position ', '').split()
    for i in mess:
        try:
            strategy = None
            if ':' in i:
                strategy = i[i.find(':')+1:]
                i = i[:i.find(':')]
            await stop_trading(message, i, strategy)
            await delete_currency_pair('database.db', i, strategy)
            try:
                await message.answer(f'Пара {i} була успішно видалена')
            except Exception as e:
                print(f'Exception on await send message: {e}')
        except Exception as e:
            print('Помилка при видаленні валютної пари:', e)
            try:
                await message.answer(f'Помилка при видаленні валютної пари {i}: {str(e)}')
            except Exception as e:
                print(f'Exception on await send message: {e}')

@router.message(Command('set_rsi_period'))
@check_user
async def set_period(message: Message):
    mess = message.text.replace('/set_rsi_period ', '').split()
    pairs = mess[:-1]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_rsi_period('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено період у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні періодів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('set_type_rsi'))
@check_user
async def set_type(message: Message):
    mess = message.text.replace('/set_type_rsi ', '').split()
    pairs = mess[:-1]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_rsi_type('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено тип у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні типів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('set_stop_loss'))
@check_user
async def set_stop_loss(message: Message):
    mess = message.text.replace('/set_stop_loss ', '').split()
    pairs = mess[:-1]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_stop_loss('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено стоп лосс у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні стоп лоссів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('set_take_profit'))
@check_user
async def set_take_profit(message: Message):
    mess = message.text.replace('/set_take_profit ', '').split()
    pairs = mess[:-3]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_take_profit('database.db', i, strategy, mess[-3], mess[-2], mess[-1])
            try:
                await message.answer(f'Успішно змінено тейк профіти у пари {i} на {mess[-3]}, {mess[-2]} і {mess[-1]} відповідно')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні тейк профітів для однієї із пар: {e}')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('set_limit_percent'))
@check_user
async def set_limit_percent(message: Message):
    mess = message.text.replace('/set_limit_percent ', '').split()
    pairs = mess[:-1]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_limit_percent('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено відсоток для ліміт-ордеру у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні відсотка ліміт ордерів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')

@router.message(Command('set_limit_x'))
@check_user
async def set_limit_x(message: Message):
    mess = message.text.replace('/set_limit_x ', '').split()
    pairs = mess[:-1]
    strategy = None
    try:
        for i in pairs:
            if ':' in i:
                strategy = i[i.find(':') + 1:]
                i = i[:i.find(':')]
            await update_limit_x('database.db', i, strategy, mess[-1])
            try:
                await message.answer(f'Успішно змінено множник для ліміт ордеру у пари {i} на {mess[-1]}')
            except Exception as e:
                print(f'Exception on await send message: {e}')
    except Exception as e:
        try:
            await message.answer(f'Помилка при зміненні множника ліміт ордерів для однієї із пар')
        except Exception as e:
            print(f'Exception on await send message: {e}')


