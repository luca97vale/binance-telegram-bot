# telegram_client.py
import httpx
import logging
from decimal import Decimal
from typing import Optional

from dto.totalDTO import totalDTO, totalDTOList

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, bot_url: str, chat_id: str):
        self.bot_url = bot_url.rstrip('/')
        self.chat_id = chat_id
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_portfolio_total(self) -> Optional[Decimal]:
        """
        Call the /total endpoint and extract total value
        Assumes the response contains the total value in a parseable format
        """
        try:
            # Call the /total endpoint (adjust URL as needed)
            response = await self.client.get(f"{self.bot_url}/portfolio/total")

            if response.status_code == 200:
                # Parse the response - adjust based on your actual response format
                totals = response.json()
                totals = totalDTOList(**totals)
                # Example parsing - modify based on your actual response structure
                if totals is not None:
                    return Decimal(sum (t.value_usd for t in totals.items))
                else:
                    logger.error("❌ Unexpected response format")
                    return None

            else:
                logger.error(f"❌ HTTP error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Error calling telegram bot: {e}")
            return None

    def _extract_total_from_message(self, message: str) -> Optional[Decimal]:
        """
        Extract total value from message text
        Looks for patterns like "Total Value: $1234.56"
        """
        import re

        try:
            # Look for patterns like "Total Value: $1234.56" or "total wallet value: $1234.56"
            patterns = [
                r'Total Value:\s*\$?([\d,]+\.?\d*)',
                r'total wallet value:\s*\$?([\d,]+\.?\d*)',
                r'Total:\s*\$?([\d,]+\.?\d*)',
            ]

            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    value_str = match.group(1).replace(',', '')
                    return Decimal(value_str)

            logger.error(f"❌ Could not parse total value from message: {message}")
            return None

        except Exception as e:
            logger.error(f"❌ Error parsing message: {e}")
            return None

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

