"""Facebook Messenger Graph API client."""
import logging
from typing import Optional
import httpx

from models import Channel

logger = logging.getLogger(__name__)


class FacebookClient:
    """Facebook Messenger Graph API client."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, channel: Channel):
        """
        Initialize Facebook client.

        Args:
            channel: Channel model with Facebook access token
        """
        self.channel = channel
        self.access_token = channel.access_token
        self.page_id = channel.extra_data.get("page_id")

    async def send_text_message(
        self,
        recipient_id: str,
        text: str,
    ) -> bool:
        """
        Send a text message to a user.

        Args:
            recipient_id: Facebook user ID
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/{self.page_id}/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "text": text,
                },
            }
            params = {"access_token": self.access_token}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

            logger.info(f"Facebook message sent to {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Facebook message: {str(e)}")
            return False

    async def send_generic_template(
        self,
        recipient_id: str,
        elements: list,
    ) -> bool:
        """
        Send a generic template message (carousel).

        Args:
            recipient_id: Facebook user ID
            elements: List of template elements

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/{self.page_id}/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": elements,
                        },
                    },
                },
            }
            params = {"access_token": self.access_token}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

            logger.info(f"Facebook generic template sent to {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Facebook generic template: {str(e)}")
            return False

    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile information.

        Args:
            user_id: Facebook user ID

        Returns:
            User profile dict or None if failed
        """
        try:
            url = f"{self.BASE_URL}/{user_id}"
            params = {
                "fields": "first_name,last_name,profile_pic_url,locale,timezone",
                "access_token": self.access_token,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting Facebook user profile: {str(e)}")
            return None

    async def set_typing_indicator(
        self,
        recipient_id: str,
        typing_on: bool = True,
    ) -> bool:
        """
        Set typing indicator.

        Args:
            recipient_id: Facebook user ID
            typing_on: True to show typing, False to hide

        Returns:
            True if indicator was set successfully
        """
        try:
            url = f"{self.BASE_URL}/{self.page_id}/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "sender_action": "typing_on" if typing_on else "typing_off",
            }
            params = {"access_token": self.access_token}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

            logger.info(f"Facebook typing indicator set for {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error setting Facebook typing indicator: {str(e)}")
            return False

    async def validate_webhook_token(self, token: str) -> bool:
        """
        Validate webhook token.

        Args:
            token: Token from webhook query parameter

        Returns:
            True if token is valid
        """
        verify_token = self.channel.extra_data.get("verify_token", "")
        return token == verify_token
