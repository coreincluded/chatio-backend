"""Twitter/X API client."""
import logging
from typing import Optional
import httpx

from models import Channel

logger = logging.getLogger(__name__)


class TwitterClient:
    """Twitter/X API v2 client."""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self, channel: Channel):
        """
        Initialize Twitter/X client.

        Args:
            channel: Channel model with Twitter access token
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
        Send a direct message to a user.

        Args:
            user_id: Twitter user ID
            text: Message text

        Returns:
            True if message was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/dm_conversations/with/{user_id}/dm_events"
            payload = {
                "text": text,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"Twitter message sent to {user_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Twitter message: {str(e)}")
            return False

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """
        Get user information.

        Args:
            user_id: Twitter user ID

        Returns:
            User info dict or None if failed
        """
        try:
            url = f"{self.BASE_URL}/users/{user_id}"
            params = {
                "user.fields": "created_at,description,public_metrics,verified",
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()

            return response.json().get("data")

        except httpx.HTTPError as e:
            logger.error(f"Error getting Twitter user info: {str(e)}")
            return None

    async def send_reply_to_tweet(
        self,
        tweet_id: str,
        text: str,
    ) -> bool:
        """
        Send a reply to a tweet.

        Args:
            tweet_id: Tweet ID to reply to
            text: Reply text

        Returns:
            True if reply was sent successfully
        """
        try:
            url = f"{self.BASE_URL}/tweets"
            payload = {
                "text": text,
                "reply": {
                    "in_reply_to_tweet_id": tweet_id,
                },
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

            logger.info(f"Twitter reply sent to tweet {tweet_id}")
            return True

        except httpx.HTTPError as e:
            logger.error(f"Error sending Twitter reply: {str(e)}")
            return False

    async def validate_webhook_signature(
        self,
        body: bytes,
        signature: str,
    ) -> bool:
        """
        Validate Twitter webhook signature.

        Args:
            body: Request body
            signature: X-Twitter-Webhooks-Signature-256 header value

        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        import base64

        try:
            webhook_secret = self.channel.extra_data.get("webhook_secret", "")
            if not webhook_secret:
                logger.warning("Webhook secret not found in extra_data")
                return False

            expected_signature = base64.b64encode(
                hmac.new(
                    webhook_secret.encode(),
                    body,
                    hashlib.sha256,
                ).digest()
            ).decode()

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error validating webhook signature: {str(e)}")
            return False
