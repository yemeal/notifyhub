import redis

from src.app.core.settings import get_settings

settings = get_settings()


def get_redis_client() -> redis.Redis:
    # decode_responses=True чтобы Redis возвращал строки (str), а не байты (bytes).
    # Это упрощает работу с ключами и значениями (не нужно вызывать .decode() вручную).
    return redis.from_url(settings.RESULT_BACKEND, decode_responses=True)
