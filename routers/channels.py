"""Channels router for managing connected channels."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Organization, Channel, ChannelType
from schemas import ChannelCreate, ChannelUpdate, ChannelResponse
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/channels", tags=["channels"])


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


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    org_id: int,
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    """Create a new connected channel."""
    # Verify org access
    org = verify_org_access(current_user, org_id, db)

    # Check if channel already exists
    existing_channel = db.query(Channel).filter(
        Channel.organization_id == org_id,
        Channel.external_channel_id == channel_data.external_channel_id,
    ).first()
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel already connected",
        )

    # Create new channel
    new_channel = Channel(
        organization_id=org_id,
        name=channel_data.name,
        channel_type=channel_data.channel_type,
        external_channel_id=channel_data.external_channel_id,
        access_token=channel_data.access_token,
    )

    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)
    return new_channel


@router.get("", response_model=List[ChannelResponse])
async def list_channels(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Channel]:
    """List all channels for an organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    channels = db.query(Channel).filter(Channel.organization_id == org_id).all()
    return channels


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    org_id: int,
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    """Get a specific channel."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.organization_id == org_id,
    ).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    return channel


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    org_id: int,
    channel_id: int,
    channel_data: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    """Update a channel."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.organization_id == org_id,
    ).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Update fields
    update_data = channel_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)

    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    org_id: int,
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete (disconnect) a channel."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    channel = db.query(Channel).filter(
        Channel.id == channel_id,
        Channel.organization_id == org_id,
    ).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    db.delete(channel)
    db.commit()
