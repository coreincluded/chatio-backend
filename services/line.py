"""LINE Messaging API client."""
import logging
from typing import Optional
import httpx

from models import Channel

logger = logging.getLogger(__name__)


class LINEClient:
    """LINE Messaging API client."""

    BASE_URL = "https://api.line.biz/v1"
    MESSAGING_API_URL = "https://api.line.biz/v1"

    def __init__(self, channel: Channel):
        """
        Initialize LINE client.

        Args:
            channel: Channel model with LINE access token
        """
        self.channel = channel
        self.access_token = channel.access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self,
        user_id: str,
        text: str,
    ) -> bool:
        """
        Send a text message to a user.

        Args:
            user_id: LINE user ID
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.MESSAGING_API_URL}/bot/message/push"
            payload = {
                "to": user_id,
                "messages": [
                    {
                        "type": "text",
                        "text": text,
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"LINE message sent to {user_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending LINE message: {str(e)}")
            return False

    async def send_rich_menu_message(
        self,
        user_id: str,
        alt_text: str,
        items: list,
    ) -> bool:
        """
        Send a template message with rich menu.

        Args:
            user_id: LINE user ID
            alt_text: Alternative text
            items: List of menu items

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.MESSAGING_API_URL}/bot/message/push"
            payload = {
                "to": user_id,
                "messages": [
                    {
                        "type": "template",
                        "altText": alt_text,
                        "template": {
                            "type": "buttons",
                            "text": alt_text,
                            "actions": items,
                        },
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"LINE rich menu message sent to {user_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending LINE rich menu: {str(e)}")
            return False

    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile information.

        Args:
            user_id: LINE user ID

        Returns:
            User profile dict or None if failed
        """
        try:
            url = f"{self.MESSAGING_API_URL}/bot/profile/{user_id}"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting LINE user profile: {str(e)}")
            return None

    async def validate_webhook_signature(
        self,
        body: bytes,
        signature: str,
    ) -> bool:
        """
        Validate LINE webhook signature.

        Args:
            body: Request body
            signature: X-Line-Signature header value (base64 encoded)

        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        import base64

        try:
            channel_secret = self.channel.extra_data.get("channel_secret", "")
            if not channel_secret:
                logger.warning("Channel secret not found in extra_data")
                return False

            # Generate expected signature
            expected_signature = base64.b64encode(
                hmac.new(
                    channel_secret.encode(),
                    body,
                    hashlib.sha256,
                ).digest()
            ).decode()

            # Compare signatures (signature is already base64 encoded from header)
            is_valid = hmac.compare_digest(signature or "", expected_signature)

            if not is_valid:
                logger.debug(f"Expected: {expected_signature}, Got: {signature}")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating webhook signature: {str(e)}")
            return False
