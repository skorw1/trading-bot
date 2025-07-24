from binance import AsyncClient

client = None

async def create_client(api_key, secret_key):
    """
    Создаёт глобальный экземпляр клиента Binance.
    """
    global client
    if client is None:
        client = await AsyncClient.create(api_key, secret_key)
        print("Клиент Binance создан.")
    else:
        print("Клиент Binance уже существует.")

async def close_client():
    """
    Закрывает глобальный экземпляр клиента Binance, если он существует.
    """
    global client
    if client is not None:
        await client.close_connection()
        client = None
        print("Клиент Binance закрыт.")
    else:
        print("Клиент Binance уже был закрыт.")