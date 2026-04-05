"""Instagram Direct Messages Graph API client."""
import logging
from typing import Optional
import httpx

from models import Channel

logger = logging.getLogger(__name__)


class InstagramClient:
    """Instagram Direct Messages Graph API client."""

    BASE_URL = "https://graph.instagram.com/v18.0"

    def __init__(self, channel: Channel):
        """
        Initialize Instagram client.

        Args:
            channel: Channel model with Instagram access token
        """
        self.channel = channel
        self.access_token = channel.access_token
        self.business_account_id = channel.extra_data.get("business_account_id")

    async def send_text_message(
        self,
        recipient_id: str,
        text: str,
    ) -> bool:
        """
        Send a text message to a user.

        Args:
            recipient_id: Instagram recipient ID
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/{self.business_account_id}/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "message": {
                    "text": text,
                },
            }
            params = {"access_token": self.access_token}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

            logger.info(f"Instagram message sent to {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Instagram message: {str(e)}")
            return False

    async def send_attachment_message(
        self,
        recipient_id: str,
        attachment_url: str,
        attachment_type: str = "image",
    ) -> bool:
        """
        Send an attachment message (image, video, etc).

        Args:
            recipient_id: Instagram recipient ID
            attachment_url: URL of the attachment
            attachment_type: Type of attachment (image, video, etc.)

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/{self.business_account_id}/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "message": {
                    "attachment": {
                        "type": attachment_type,
                        "payload": {
                            "url": attachment_url,
                        },
                    },
                },
            }
            params = {"access_token": self.access_token}

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, params=params)
                response.raise_for_status()

            logger.info(f"Instagram attachment message sent to {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Instagram attachment: {str(e)}")
            return False

    async def get_conversations(self, limit: int = 20) -> Optional[list]:
        """
        Get list of conversations.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversations or None if failed
        """
        try:
            url = f"{self.BASE_URL}/{self.business_account_id}/conversations"
            params = {
                "fields": "id,senders,updated_time,snippet",
                "limit": limit,
                "access_token": self.access_token,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            return response.json().get("data", [])

        except httpx.HTTPError as e:
            logger.error(f"Error getting Instagram conversations: {str(e)}")
            return None

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> Optional[list]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: Instagram conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of messages or None if failed
        """
        try:
            url = f"{self.BASE_URL}/{conversation_id}/messages"
            params = {
                "fields": "id,message,timestamp,from",
                "limit": limit,
                "access_token": self.access_token,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            return response.json().get("data", [])

        except httpx.HTTPError as e:
            logger.error(f"Error getting Instagram messages: {str(e)}")
            return None

    async def get_profile_info(self) -> Optional[dict]:
        """
        Get business profile information.

        Args:
            Returns:
            Profile dict or None if failed
        """
        try:
            url = f"{self.BASE_URL}/{self.business_account_id}"
            params = {
                "fields": "id,name,username,profile_picture_url,biography",
                "access_token": self.access_token,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting Instagram profile info: {str(e)}")
            return None
