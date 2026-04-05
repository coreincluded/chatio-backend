"""LinkedIn API client."""
import logging
from typing import Optional
import httpx

from models import Channel

logger = logging.getLogger(__name__)


class LinkedInClient:
    """LinkedIn REST API client."""

    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, channel: Channel):
        """
        Initialize LinkedIn client.

        Args:
            channel: Channel model with LinkedIn access token
        """
        self.channel = channel
        self.access_token = channel.access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def send_direct_message(
        self,
        recipient_id: str,
        text: str,
    ) -> bool:
        """
        Send a direct message to a LinkedIn user.

        Args:
            recipient_id: LinkedIn recipient ID
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/messaging/conversations"
            payload = {
                "recipients": {
                    "values": [recipient_id],
                },
                "subject": "",
                "body": text,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"LinkedIn message sent to {recipient_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending LinkedIn message: {str(e)}")
            return False

    async def get_user_profile(self) -> Optional[dict]:
        """
        Get authenticated user profile information.

        Returns:
            User profile dict or None if failed
        """
        try:
            url = f"{self.BASE_URL}/me"
            params = {
                "projection": "(id,localizedFirstName,localizedLastName,profilePicture)",
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting LinkedIn user profile: {str(e)}")
            return None

    async def share_post(
        self,
        text: str,
        media_url: Optional[str] = None,
    ) -> bool:
        """
        Share a post on LinkedIn.

        Args:
            text: Post text
            media_url: Optional media URL to attach

        Returns:
            True if post was shared successfully
        """
        try:
            url = f"{self.BASE_URL}/ugcPosts"
            payload = {
                "author": f"urn:li:person:{self.channel.external_channel_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareMediaCategory": "IMAGE" if media_url else "NONE",
                        "shareCommentary": {
                            "text": text,
                        },
                    },
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
                },
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"LinkedIn post shared by {self.channel.external_channel_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sharing LinkedIn post: {str(e)}")
            return False

    async def get_conversation_history(
        self,
        conversation_id: str,
    ) -> Optional[list]:
        """
        Get message history for a conversation.

        Args:
            conversation_id: LinkedIn conversation ID

        Returns:
            List of messages or None if failed
        """
        try:
            url = f"{self.BASE_URL}/conversations/{conversation_id}"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting LinkedIn conversation: {str(e)}")
            return None
