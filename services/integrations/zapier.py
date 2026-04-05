"""Zapier webhook integration connector."""
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseIntegration

logger = logging.getLogger(__name__)


class ZapierIntegration(BaseIntegration):
    """Zapier webhook integration for sending events."""

    def __init__(self, organization_id: int, config: Dict[str, Any]):
        """Initialize Zapier integration."""
        super().__init__(organization_id, "zapier", config)
        self.base_url = "https://hooks.zapier.com/hooks/catch"

    async def connect(self) -> bool:
        """
        Test connection by sending a test event to Zapier webhook.

        Returns:
            True if webhook is reachable
        """
        try:
            webhook_url = self._get_webhook_url()
            if not webhook_url:
                logger.error("Zapier webhook URL not configured")
                return False

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    webhook_url,
                    json={
                        "test": True,
                        "timestamp": datetime.utcnow().isoformat(),
                        "organization_id": self.organization_id,
                    },
                )
                response.raise_for_status()
                logger.info(f"Zapier connection test successful for org {self.organization_id}")
                return True

        except Exception as e:
            logger.error(f"Zapier connection test failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect Zapier integration (clear webhook URL).

        Returns:
            Always True (no external cleanup needed)
        """
        self.config.pop("webhook_url", None)
        logger.info(f"Zapier integration disconnected for org {self.organization_id}")
        return True

    async def sync(self) -> Dict[str, Any]:
        """
        Zapier doesn't support pull-based sync (webhook only).

        Returns:
            Empty sync result
        """
        return {
            "synced_count": 0,
            "errors": [],
            "message": "Zapier uses push-based webhooks. No manual sync available.",
        }

    async def webhook_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Zapier.

        Args:
            payload: Event payload from Zapier

        Returns:
            Response with event type and processing status
        """
        try:
            event_type = payload.get("type", "unknown")
            logger.info(f"Received Zapier webhook: {event_type} for org {self.organization_id}")

            # Process the event based on type
            # This would be extended based on actual Zapier trigger types
            return {
                "success": True,
                "event_type": event_type,
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error handling Zapier webhook: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }

    async def send_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """
        Send an event to Zapier.

        Args:
            event_type: Type of event (message.received, conversation.started, etc.)
            event_data: Event data to send

        Returns:
            True if event was sent successfully
        """
        try:
            webhook_url = self._get_webhook_url()
            if not webhook_url:
                logger.warning("Zapier webhook URL not configured")
                return False

            payload = {
                "event_type": event_type,
                "organization_id": self.organization_id,
                "data": event_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Zapier event sent: {event_type}")
                return True

        except Exception as e:
            logger.error(f"Error sending event to Zapier: {str(e)}")
            return False
