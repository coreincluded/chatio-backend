"""Automations router for managing automation rules."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Organization, Automation
from schemas import AutomationCreate, AutomationUpdate, AutomationResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/automations", tags=["automations"])


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


@router.post("", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
async def create_automation(
    org_id: int,
    automation_data: AutomationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Automation:
    """Create a new automation rule."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Create new automation
    new_automation = Automation(
        organization_id=org_id,
        name=automation_data.name,
        description=automation_data.description,
        trigger_type=automation_data.trigger_type,
        trigger_value=automation_data.trigger_value,
        action_type=automation_data.action_type,
        action_value=automation_data.action_value,
        priority=automation_data.priority,
    )

    db.add(new_automation)
    db.commit()
    db.refresh(new_automation)
    return new_automation


@router.get("", response_model=List[AutomationResponse])
async def list_automations(
    org_id: int,
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Automation]:
    """List all automations for an organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    query = db.query(Automation).filter(Automation.organization_id == org_id)

    if active_only:
        query = query.filter(Automation.is_active == True)

    # Order by priority (descending) then by creation date
    automations = query.order_by(
        Automation.priority.desc(),
        Automation.created_at.desc(),
    ).limit(limit).offset(offset).all()

    return automations


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    org_id: int,
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Automation:
    """Get a specific automation rule."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    automation = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.organization_id == org_id,
    ).first()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    return automation


@router.patch("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    org_id: int,
    automation_id: int,
    automation_data: AutomationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Automation:
    """Update an automation rule."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    automation = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.organization_id == org_id,
    ).first()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    # Update fields
    update_data = automation_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(automation, field, value)

    db.commit()
    db.refresh(automation)
    return automation


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    org_id: int,
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete an automation rule."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    automation = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.organization_id == org_id,
    ).first()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    db.delete(automation)
    db.commit()


@router.post("/{automation_id}/toggle", response_model=AutomationResponse)
async def toggle_automation(
    org_id: int,
    automation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Automation:
    """Toggle automation active status."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    automation = db.query(Automation).filter(
        Automation.id == automation_id,
        Automation.organization_id == org_id,
    ).first()

    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation not found",
        )

    automation.is_active = not automation.is_active
    db.commit()
    db.refresh(automation)
    return automation
