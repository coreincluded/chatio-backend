"""Base integration connector abstract class."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseIntegration(ABC):
    """Abstract base class for all integrations."""

    def __init__(self, organization_id: int, provider: str, config: Dict[str, Any]):
        """
        Initialize integration.

        Args:
            organization_id: Organization ID
            provider: Integration provider name (zapier, hubspot, shopify, google_calendar)
            config: Integration configuration (API key, webhook URL, etc.)
        """
        self.organization_id = organization_id
        self.provider = provider
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """
        Test connection and validate credentials.

        Returns:
            True if connection is successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect the integration.

        Returns:
            True if disconnection is successful
        """
        pass

    @abstractmethod
    async def sync(self) -> Dict[str, Any]:
        """
        Perform a full sync with the service.

        Returns:
            Sync result with stats (synced_count, errors, etc.)
        """
        pass

    @abstractmethod
    async def webhook_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from the service.

        Args:
            payload: Webhook payload from the service

        Returns:
            Response indicating success/failure
        """
        pass

    def _get_api_key(self) -> Optional[str]:
        """Get API key from config."""
        return self.config.get("api_key")

    def _get_webhook_url(self) -> Optional[str]:
        """Get webhook URL from config."""
        return self.config.get("webhook_url")
