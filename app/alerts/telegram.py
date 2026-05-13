import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """Sends plain-text alerts to a Telegram chat via Bot API."""

    _API = "https://api.telegram.org/bot{token}/sendMessage"

    def send(self, message: str) -> bool:
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.info("Telegram not configured — skipping alert")
            return False

        url = self._API.format(token=settings.TELEGRAM_BOT_TOKEN)
        try:
            resp = httpx.post(
                url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
