"""Shopify integration connector."""
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseIntegration

logger = logging.getLogger(__name__)


class ShopifyIntegration(BaseIntegration):
    """Shopify integration for order lookup and product queries."""

    def __init__(self, organization_id: int, config: Dict[str, Any]):
        """Initialize Shopify integration."""
        super().__init__(organization_id, "shopify", config)
        self.shop_domain = config.get("shop_domain", "")
        self.base_url = f"https://{self.shop_domain}/admin/api/2024-01"

    async def connect(self) -> bool:
        """
        Test connection to Shopify API.

        Returns:
            True if API credentials are valid
        """
        try:
            api_key = self._get_api_key()
            if not api_key or not self.shop_domain:
                logger.error("Shopify API key or shop domain not configured")
                return False

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/shop.json",
                    headers={"X-Shopify-Access-Token": api_key},
                )
                response.raise_for_status()
                logger.info(f"Shopify connection successful for org {self.organization_id}")
                return True

        except Exception as e:
            logger.error(f"Shopify connection test failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect Shopify integration.

        Returns:
            Always True
        """
        self.config.pop("api_key", None)
        self.config.pop("shop_domain", None)
        logger.info(f"Shopify integration disconnected for org {self.organization_id}")
        return True

    async def sync(self) -> Dict[str, Any]:
        """
        Sync products from Shopify (sample implementation).

        Returns:
            Sync result with stats
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                return {"synced_count": 0, "errors": ["API key not configured"]}

            synced_count = 0

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/products.json",
                    headers={"X-Shopify-Access-Token": api_key},
                    params={"limit": 250},
                )
                response.raise_for_status()
                data = response.json()
                synced_count = len(data.get("products", []))

            logger.info(f"Shopify sync completed: {synced_count} products synced")
            return {"synced_count": synced_count, "errors": []}

        except Exception as e:
            logger.error(f"Error syncing Shopify products: {str(e)}")
            return {"synced_count": 0, "errors": [str(e)]}

    async def webhook_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Shopify.

        Args:
            payload: Webhook payload from Shopify

        Returns:
            Response with processing status
        """
        try:
            event_type = payload.get("type", "unknown")
            logger.info(f"Received Shopify webhook: {event_type} for org {self.organization_id}")
            return {
                "success": True,
                "event_type": event_type,
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error handling Shopify webhook: {str(e)}")
            return {"success": False, "error": str(e)}

    async def lookup_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up an order in Shopify.

        Args:
            order_id: Shopify order ID

        Returns:
            Order details if found
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                logger.error("Shopify API key not configured")
                return None

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/orders/{order_id}.json",
                    headers={"X-Shopify-Access-Token": api_key},
                )
                response.raise_for_status()
                data = response.json()
                return data.get("order")

        except Exception as e:
            logger.error(f"Error looking up Shopify order: {str(e)}")
            return None

    async def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for products in Shopify.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of matching products
        """
        try:
            api_key = self._get_api_key()
            if not api_key:
                logger.error("Shopify API key not configured")
                return []

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/products.json",
                    headers={"X-Shopify-Access-Token": api_key},
                    params={"limit": limit, "fields": "id,title,handle,image"},
                )
                response.raise_for_status()
                products = response.json().get("products", [])

                # Filter by query
                query_lower = query.lower()
                filtered = [p for p in products if query_lower in p.get("title", "").lower()]
                return filtered[:limit]

        except Exception as e:
            logger.error(f"Error searching Shopify products: {str(e)}")
            return []
