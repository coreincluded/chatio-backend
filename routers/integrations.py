"""Integrations router for third-party service connectors."""
import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import Integration, Organization
from schemas import IntegrationResponse, IntegrationCreate, IntegrationConfig
from services.integrations import (
    ZapierIntegration,
    HubSpotIntegration,
    ShopifyIntegration,
    GoogleCalendarIntegration,
)
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


def get_integration_instance(provider: str, config: Dict[str, Any]):
    """Factory function to instantiate correct integration class."""
    provider_map = {
        "zapier": ZapierIntegration,
        "hubspot": HubSpotIntegration,
        "shopify": ShopifyIntegration,
        "google_calendar": GoogleCalendarIntegration,
    }

    IntegrationClass = provider_map.get(provider)
    if not IntegrationClass:
        raise ValueError(f"Unknown integration provider: {provider}")

    return IntegrationClass(1, config)  # org_id will be set by caller


@router.get("", response_model=List[Dict[str, Any]])
async def list_integrations(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available integrations and their connection status."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Get all connected integrations for this org
    connected = db.query(Integration).filter(
        Integration.organization_id == org.id
    ).all()

    # Map to response with status
    connected_map = {i.provider: i for i in connected}

    available_providers = [
        {
            "provider": "zapier",
            "name": "Zapier",
            "description": "Send Chatio events to Zapier workflows",
            "icon": "⚡",
            "status": "connected" if "zapier" in connected_map else "disconnected",
            "is_active": connected_map["zapier"].is_active if "zapier" in connected_map else False,
        },
        {
            "provider": "hubspot",
            "name": "HubSpot",
            "description": "Sync contacts and create deals in HubSpot CRM",
            "icon": "📊",
            "status": "connected" if "hubspot" in connected_map else "disconnected",
            "is_active": connected_map["hubspot"].is_active if "hubspot" in connected_map else False,
        },
        {
            "provider": "shopify",
            "name": "Shopify",
            "description": "Look up orders and products from Shopify",
            "icon": "🛒",
            "status": "connected" if "shopify" in connected_map else "disconnected",
            "is_active": connected_map["shopify"].is_active if "shopify" in connected_map else False,
        },
        {
            "provider": "google_calendar",
            "name": "Google Calendar",
            "description": "Manage appointments and calendar events",
            "icon": "📅",
            "status": "connected" if "google_calendar" in connected_map else "disconnected",
            "is_active": connected_map["google_calendar"].is_active if "google_calendar" in connected_map else False,
        },
    ]

    return available_providers


@router.post("/{provider}/connect", response_model=IntegrationResponse)
async def connect_integration(
    provider: str,
    config: IntegrationConfig,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connect an integration by storing credentials."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate provider
    valid_providers = ["zapier", "hubspot", "shopify", "google_calendar"]
    if provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Check if already connected
    existing = db.query(Integration).filter(
        Integration.organization_id == org.id,
        Integration.provider == provider,
    ).first()

    config_dict = config.dict(exclude_unset=True)
    config_json = json.dumps(config_dict)

    try:
        # Test connection
        integration = get_integration_instance(provider, config_dict)
        integration.organization_id = org.id

        is_valid = await integration.connect()
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to {provider}. Please check your credentials.",
            )

        # Save or update integration
        if existing:
            existing.config = config_json
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            db.commit()
            return IntegrationResponse.from_orm(existing)
        else:
            integration_record = Integration(
                organization_id=org.id,
                provider=provider,
                config=config_json,
                is_active=True,
            )
            db.add(integration_record)
            db.commit()
            db.refresh(integration_record)
            return IntegrationResponse.from_orm(integration_record)

    except Exception as e:
        db.rollback()
        logger.error(f"Error connecting integration: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect {provider}: {str(e)}",
        )


@router.delete("/{provider}/disconnect")
async def disconnect_integration(
    provider: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect an integration."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    integration = db.query(Integration).filter(
        Integration.organization_id == org.id,
        Integration.provider == provider,
    ).first()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    db.delete(integration)
    db.commit()

    return {"message": f"Integration {provider} disconnected successfully"}


@router.post("/{provider}/webhook")
async def receive_webhook(
    provider: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Receive webhook from integration service."""
    try:
        # In a real implementation, you'd look up the integration by provider
        # For now, just log the webhook
        logger.info(f"Received webhook from {provider}: {payload}")
        return {"success": True, "message": f"Webhook from {provider} received"}

    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider}/sync")
async def trigger_sync(
    provider: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a sync for an integration."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    integration = db.query(Integration).filter(
        Integration.organization_id == org.id,
        Integration.provider == provider,
    ).first()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        config_dict = json.loads(integration.config)
        integration_instance = get_integration_instance(provider, config_dict)
        integration_instance.organization_id = org.id

        result = await integration_instance.sync()

        # Update last_synced timestamp
        integration.last_synced = datetime.utcnow()
        db.commit()

        return {
            "provider": provider,
            "synced_count": result.get("synced_count", 0),
            "errors": result.get("errors", []),
            "message": result.get("message", "Sync completed"),
        }

    except Exception as e:
        logger.error(f"Error syncing integration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
