start_message = """
Команда: /create_position
Опис: Створює нову торгову позицію для вказаної валютної пари з початковими параметрами.
Аргументи: <pair_name> <pair_name2> <update_interval> <timeframe> <position_size> <leverage> <rsi_лонг> <минуле rsi_long> <rsi_short> <минуле rsi_short> <rsi_period> <rsi type> <stop_loss> <take_profit1> <take_profit2> <take_profit3> <limit_percent> <limit_x>
Приклад використання: /create_position BTCUSDT:Стратегія ETHUSDT 60 1m 100 50 10 10 90 90 1 close 0.3 2 4 6 5 20

Команда: /delete_position
Опис: Видаляє валютну пару
Аргументи: <pair_name>
Приклад використання: /delete_position BTCUSDT ETHUSDT

Команда: /set_update_interval
Опис: Змінює час оновлення даних для вказаної валютної пари.
Аргументи: <pair_name> <new_interval>
Приклад використання: /set_update_interval BTCUSDT ETHUSDT 120

Команда: /set_timeframe
Опис: Змінює таймфрейм для вказаної валютної пари. (Мінімальний таймфрейм - 1m)
Аргументи: <pair_name> <new_timeframe>
Приклад використання: /set_timeframe BTCUSDT ETHUSDT 4h

Команда: /set_position_size
Опис: Змінює розмір позиції без урахування кредитного плеча для вказаної валютної пари.
Аргументи: <pair_name> <new_position_size>
Приклад використання: /set_position_size BTCUSDT ETHUSDT 150

Команда: /set_leverage
Опис: Змінює кредитне плече для вказаної валютної пари.
Аргументи: <pair_name> <new_leverage>
Приклад використання: /set_leverage BTCUSDT ETHUSDT 100

Команда: /view_position
Опис: Показує поточні параметри для вказаної валютної пари.
Аргументи: <pair_name>
Приклад використання: /view_position BTCUSDT

Команда: /view_positions
Опис: Показує усі додані валютні пари
Аргументи: ніяких
Приклад використання: /view_positions

Команда: /start_trade
Опис: Запускає торговлю парою
Аргументи: <pair_name>
Приклад використання: /start_trade BTCUSDT ETHUSDT

Команда: /stop_trade
Опис: Остановлює торговлю парою
Аргументи: <pair_name>
Приклад використання: /stop_trade BTCUSDT ETHUSDT

Команда: /set_rsi_period
Опис: Змінює період RSI
Аргументи: <pair_name> <period>
Приклад використання: /set_rsi_period BTCUSDT ETHUSDT 5

Команда: /set_type_rsi
Опис: Змінює тип RSI
Аргументи: <pair_name> <type>
Приклад використання: /set_type_rsi BTCUSDT ETHUSDT close

Команда: /set_stop_loss
Опис: Змінює стоп лосс
Аргументи: <pair_name> <stop_loss>
Приклад використання: /set_stop_loss BTCUSDT ETHUSDT 2.5

Команда: /set_take_profit
Опис: Змінює тейк профіт
Аргументи: <pair_name> <take_profit1> <take_profit2> <take_profit3>
Приклад використання: /set_take_profit BTCUSDT ETHUSDT 2.5 5 8

Команда: /set_limit_percent
Опис: Змінює відсоток для ліміт ордеру
Аргументи: <pair_name> <limit_percent>
Приклад використання: /set_limit_percent BTCUSDT ETHUSDT 2.5

Команда: /set_limit_x
Опис: Змінює множник для ліміт ордеру
Аргументи: <pair_name> <limit_x>
Приклад використання: /set_limit_x BTCUSDT ETHUSDT 2 (ціле число)




"""