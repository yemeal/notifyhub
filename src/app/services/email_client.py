import random


class ServiceUnavailableError(Exception):
    """Имитирует временную недоступность (503)"""

    pass


class ConnectionTimeoutError(Exception):
    """Имитирует таймаут соединения"""

    pass


class UnreliableEmailClient:
    @staticmethod
    def send(recipient: str, subject: str, body: str) -> None:
        """имитирует отправку письма с вероятностью ошибки"""
        val = random.random()
        if val < 0.60:
            raise ServiceUnavailableError("SMTP Service Unavailable (503)")
        elif val < 0.80:
            raise ConnectionTimeoutError("SMTP Connection Timeout")
        else:
            return
