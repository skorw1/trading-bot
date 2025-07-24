import aiosqlite

async def create_tables(db_path='database.db'):
    async with aiosqlite.connect(db_path) as db:
        # Створення таблиці для валютних пар
        await db.execute('''
            CREATE TABLE IF NOT EXISTS currency_pair (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_name TEXT NOT NULL,             -- Назва валютної пари
                strategy_name TEXT DEFAULT NULL,     -- Назва стратегії (може бути NULL)
                update_interval INTEGER NOT NULL,    -- Час оновлення в секундах
                timeframe TEXT NOT NULL,             -- Таймфрейм, напр. '1m', '1h', '1d'
                position_size REAL NOT NULL,         -- Розмір позиції без кредитного плеча
                leverage INTEGER NOT NULL,           -- Кредитне плече
                rsi_long REAL NOT NULL,              -- Значення RSI для відкриття довгої позиції
                prev_rsi_long REAL NOT NULL,         -- Попереднє значення RSI для відкриття довгої позиції
                rsi_short REAL NOT NULL,             -- Значення RSI для відкриття короткої позиції
                prev_rsi_short REAL NOT NULL,        -- Попереднє значення RSI для відкриття короткої позиції
                rsi_period INTEGER NOT NULL,         -- Период RSI
                rsi_type TEXT NOT NULL,              -- Тип даних для RSI (наприклад, 'close', 'open', 'maxmin3' і т.д.)
                stop_loss REAL NOT NULL,             -- Значення стоп-лосс у відсотках (float)
                take_profit REAL NOT NULL,           -- Значення тейк-профіт у відсотках (float)
                take_profit2 REAL NOT NULL,           -- Значення тейк-профіт2 у відсотках (float)
                take_profit3 REAL NOT NULL,           -- Значення тейк-профіт3 у відсотках (float)
                limit_percent REAL NOT NULL,
                limit_x INTEGER NOT NULL,
                UNIQUE(pair_name, strategy_name)     -- Унікальне обмеження для поєднання пари та стратегії
            )
        ''')
        await db.commit()

async def get_all_currency_pairs(db_path='database.db'):
    """
    Возвращает список всех имен валютных пар (pair_name) из таблицы currency_pair.
    """
    async with aiosqlite.connect(db_path) as db:
        async with db.execute('SELECT pair_name FROM currency_pair') as cursor:
            pairs = await cursor.fetchall()  # Получаем все результаты
            return [pair[0] for pair in pairs]  # Извлекаем только имена пар

"""
Добавление валютной пары
"""
async def add_currency_pair(
        db_path, pair_name, strategy_name, update_interval, timeframe, position_size, leverage,
        rsi_long, prev_rsi_long, rsi_short, prev_rsi_short, rsi_period, rsi_type,
        stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x
):
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            INSERT INTO currency_pair (
                pair_name, strategy_name, update_interval, timeframe, position_size, leverage, 
                rsi_long, prev_rsi_long, rsi_short, prev_rsi_short, rsi_period, rsi_type, 
                stop_loss, take_profit, take_profit2, take_profit3, limit_percent, limit_x
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pair_name, strategy_name, update_interval, timeframe, position_size, leverage,
            rsi_long, prev_rsi_long, rsi_short, prev_rsi_short, rsi_period, rsi_type,
            stop_loss, take_profit1, take_profit2, take_profit3, limit_percent, limit_x
        ))
        await db.commit()


"""
Просмотр данных о валютной паре
"""
async def get_currency_pair(db_path, pair_name, strategy_name):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''
                SELECT * FROM currency_pair 
                WHERE pair_name = ? AND strategy_name IS NULL
            '''
            params = (pair_name,)
        else:
            query = '''
                SELECT * FROM currency_pair 
                WHERE pair_name = ? AND strategy_name = ?
            '''
            params = (pair_name, strategy_name)

        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return row


async def delete_currency_pair(db_path, pair_name, strategy_name):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''
                DELETE FROM currency_pair 
                WHERE pair_name = ? AND strategy_name IS NULL
            '''
            params = (pair_name,)
        else:
            query = '''
                DELETE FROM currency_pair 
                WHERE pair_name = ? AND strategy_name = ?
            '''
            params = (pair_name, strategy_name)

        await db.execute(query, params)
        await db.commit()

async def update_currency_pair_interval(db_path, pair_name, strategy_name, update_interval):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = 'UPDATE currency_pair SET update_interval = ? WHERE pair_name = ? AND strategy_name IS NULL'
            await db.execute(query, (update_interval, pair_name))
        else:
            query = 'UPDATE currency_pair SET update_interval = ? WHERE pair_name = ? AND strategy_name = ?'
            await db.execute(query, (update_interval, pair_name, strategy_name))
        await db.commit()

async def update_currency_pair_timeframe(db_path, pair_name, strategy_name, timeframe):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = 'UPDATE currency_pair SET timeframe = ? WHERE pair_name = ? AND strategy_name IS NULL'
            await db.execute(query, (timeframe, pair_name))
        else:
            query = 'UPDATE currency_pair SET timeframe = ? WHERE pair_name = ? AND strategy_name = ?'
            await db.execute(query, (timeframe, pair_name, strategy_name))
        await db.commit()

async def update_currency_pair_position_size(db_path, pair_name, strategy_name, position_size):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = 'UPDATE currency_pair SET position_size = ? WHERE pair_name = ? AND strategy_name IS NULL'
            await db.execute(query, (position_size, pair_name))
        else:
            query = 'UPDATE currency_pair SET position_size = ? WHERE pair_name = ? AND strategy_name = ?'
            await db.execute(query, (position_size, pair_name, strategy_name))
        await db.commit()

async def update_currency_pair_leverage(db_path, pair_name, strategy_name, leverage):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = 'UPDATE currency_pair SET leverage = ? WHERE pair_name = ? AND strategy_name IS NULL'
            await db.execute(query, (leverage, pair_name))
        else:
            query = 'UPDATE currency_pair SET leverage = ? WHERE pair_name = ? AND strategy_name = ?'
            await db.execute(query, (leverage, pair_name, strategy_name))
        await db.commit()

async def update_rsi_period(db_path, pair_name, strategy_name, new_rsi_period):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''UPDATE currency_pair SET rsi_period = ? WHERE pair_name = ? AND strategy_name IS NULL'''
            await db.execute(query, (new_rsi_period, pair_name))
        else:
            query = '''UPDATE currency_pair SET rsi_period = ? WHERE pair_name = ? AND strategy_name = ?'''
            await db.execute(query, (new_rsi_period, pair_name, strategy_name))
        await db.commit()

async def update_rsi_type(db_path, pair_name, strategy_name, new_rsi_type):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''UPDATE currency_pair SET rsi_type = ? WHERE pair_name = ? AND strategy_name IS NULL'''
            await db.execute(query, (new_rsi_type, pair_name))
        else:
            query = '''UPDATE currency_pair SET rsi_type = ? WHERE pair_name = ? AND strategy_name = ?'''
            await db.execute(query, (new_rsi_type, pair_name, strategy_name))
        await db.commit()

async def update_stop_loss(db_path, pair_name, strategy_name, new_stop_loss):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''UPDATE currency_pair SET stop_loss = ? WHERE pair_name = ? AND strategy_name IS NULL'''
            await db.execute(query, (new_stop_loss, pair_name))
        else:
            query = '''UPDATE currency_pair SET stop_loss = ? WHERE pair_name = ? AND strategy_name = ?'''
            await db.execute(query, (new_stop_loss, pair_name, strategy_name))
        await db.commit()

async def update_take_profit(db_path, pair_name, strategy_name, new_take_profit1, new_take_profit2, new_take_profit3):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''
                UPDATE currency_pair 
                SET take_profit = ?, take_profit2 = ?, take_profit3 = ? 
                WHERE pair_name = ? AND strategy_name IS NULL
            '''
            await db.execute(query, (new_take_profit1, new_take_profit2, new_take_profit3, pair_name))
        else:
            query = '''
                UPDATE currency_pair 
                SET take_profit = ?, take_profit2 = ?, take_profit3 = ? 
                WHERE pair_name = ? AND strategy_name = ?
            '''
            await db.execute(query, (new_take_profit1, new_take_profit2, new_take_profit3, pair_name, strategy_name))

        await db.commit()
async def update_limit_percent(db_path, pair_name, strategy_name, new_limit_percent):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''UPDATE currency_pair SET limit_percent = ? WHERE pair_name = ? AND strategy_name IS NULL'''
            await db.execute(query, (new_limit_percent, pair_name))
        else:
            query = '''UPDATE currency_pair SET limit_percent = ? WHERE pair_name = ? AND strategy_name = ?'''
            await db.execute(query, (new_limit_percent, pair_name, strategy_name))
        await db.commit()

async def update_limit_x(db_path, pair_name, strategy_name, new_limit_x):
    async with aiosqlite.connect(db_path) as db:
        if strategy_name is None:
            query = '''UPDATE currency_pair SET limit_x = ? WHERE pair_name = ? AND strategy_name IS NULL'''
            await db.execute(query, (new_limit_x, pair_name))
        else:
            query = '''UPDATE currency_pair SET limit_x = ? WHERE pair_name = ? AND strategy_name = ?'''
            await db.execute(query, (new_limit_x, pair_name, strategy_name))
        await db.commit()
