"""Automation templates router for managing template library."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Organization, Automation
from routers.auth import get_current_user
from services.automation_templates import (
    get_all_templates,
    get_template_by_id,
    list_categories,
    AutomationTemplate,
)

router = APIRouter(prefix="/api/v1/automation-templates", tags=["automation-templates"])


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_org_access(user: User, org_id: int, db: Session) -> Organization:
    """Verify user has access to organization."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or org.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization",
        )
    return org


class TemplateResponse(BaseModel):
    """Response model for automation template."""
    id: str
    name: str
    description: str
    category: str
    trigger_type: str
    action_type: str


class DetailedTemplateResponse(TemplateResponse):
    """Detailed response with config info."""
    trigger_config: dict
    action_config: dict
    is_active: bool
    priority: int


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> List[TemplateResponse]:
    """List all available automation templates."""
    templates = get_all_templates()
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            category=t.category,
            trigger_type=t.trigger_type.value,
            action_type=t.action_type,
        )
        for t in templates
    ]


@router.get("/{template_id}", response_model=DetailedTemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
) -> DetailedTemplateResponse:
    """Get detailed information about a specific template."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return DetailedTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        trigger_type=template.trigger_type.value,
        trigger_config=template.trigger_config,
        action_type=template.action_type,
        action_config=template.action_config,
        is_active=template.is_active,
        priority=template.priority,
    )


@router.post("/{template_id}/install")
async def install_template(
    template_id: str,
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Install a template as an active automation for the organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Get template
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Create automation from template
    automation_data = template.to_automation_dict(org_id)

    automation = Automation(
        organization_id=automation_data["organization_id"],
        name=automation_data["name"],
        description=automation_data["description"],
        trigger_type=automation_data["trigger_type"],
        trigger_value=automation_data["trigger_value"],
        action_type=automation_data["action_type"],
        action_value=automation_data["action_value"],
        is_active=automation_data["is_active"],
        priority=automation_data["priority"],
    )

    db.add(automation)
    db.commit()
    db.refresh(automation)

    return {
        "id": automation.id,
        "name": automation.name,
        "message": f"Template '{template.name}' installed successfully",
    }


@router.get("/categories", response_model=List[str])
async def get_categories(
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Get list of template categories."""
    return list_categories()
