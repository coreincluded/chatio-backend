"""HubSpot CRM integration connector."""
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseIntegration

logger = logging.getLogger(__name__)


class HubSpotIntegration(BaseIntegration):
    """HubSpot CRM integration for syncing contacts and creating deals."""

    def __init__(self, organization_id: int, config: Dict[str, Any]):
        """Initialize HubSpot integration."""
        super().__init__(organization_id, "hubspot", config)
        self.base_url = "https://api.hubapi.com"

    async def connect(self) -> bool:
        """
        Test connection to HubSpot API.

        Returns:
            True if API credentials are valid
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                logger.error("HubSpot API key not configured")
                return False

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/contacts",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params={"limit": 1},
                )
                response.raise_for_status()
                logger.info(f"HubSpot connection successful for org {self.organization_id}")
                return True

        except Exception as e:
            logger.error(f"HubSpot connection test failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect HubSpot integration.

        Returns:
            Always True
        """
        self.config.pop("api_key", None)
        logger.info(f"HubSpot integration disconnected for org {self.organization_id}")
        return True

    async def sync(self) -> Dict[str, Any]:
        """
        Sync contacts from HubSpot.

        Returns:
            Sync result with stats
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                return {"synced_count": 0, "errors": ["API key not configured"]}

            synced_count = 0
            errors = []

            async with httpx.AsyncClient(timeout=30) as client:
                # Get all contacts (paginated)
                after = None
                while True:
                    params = {"limit": 100}
                    if after:
                        params["after"] = after

                    response = await client.get(
                        f"{self.base_url}/crm/v3/objects/contacts",
                        headers={"Authorization": f"Bearer {api_key}"},
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()

                    contacts = data.get("results", [])
                    synced_count += len(contacts)

                    # Check for pagination
                    paging = data.get("paging", {})
                    after = paging.get("next", {}).get("after")
                    if not after:
                        break

            logger.info(f"HubSpot sync completed: {synced_count} contacts synced")
            return {"synced_count": synced_count, "errors": errors}

        except Exception as e:
            logger.error(f"Error syncing HubSpot contacts: {str(e)}")
            return {"synced_count": 0, "errors": [str(e)]}

    async def webhook_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from HubSpot.

        Args:
            payload: Webhook payload from HubSpot

        Returns:
            Response with processing status
        """
        try:
            logger.info(f"Received HubSpot webhook for org {self.organization_id}")
            return {
                "success": True,
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error handling HubSpot webhook: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_deal(
        self,
        contact_id: str,
        deal_name: str,
        deal_value: Optional[float] = None,
    ) -> Optional[str]:
        """
        Create a deal in HubSpot for a conversation.

        Args:
            contact_id: HubSpot contact ID
            deal_name: Name of the deal
            deal_value: Optional deal value in cents

        Returns:
            Deal ID if successful
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                logger.error("HubSpot API key not configured")
                return None

            properties = {
                "dealname": deal_name,
                "dealstage": "negotiation",
            }
            if deal_value:
                properties["amount"] = deal_value

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/crm/v3/objects/deals",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"properties": properties},
                )
                response.raise_for_status()
                data = response.json()
                deal_id = data.get("id")
                logger.info(f"Deal created in HubSpot: {deal_id}")
                return deal_id

        except Exception as e:
            logger.error(f"Error creating HubSpot deal: {str(e)}")
            return None
