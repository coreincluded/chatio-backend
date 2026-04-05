"""Contacts router for managing customer contacts and intelligence."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal
from models import User, Organization, Contact, ContactTag, Segment, Conversation, LifecycleStage
from schemas import (
    ContactCreate, ContactUpdate, ContactResponse, ContactDetailResponse,
    ContactTagCreate, ContactTagResponse, SegmentCreate, SegmentUpdate, SegmentResponse
)
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


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


# ============ Contacts ============

@router.get("", response_model=List[ContactResponse])
async def list_contacts(
    org_id: int = Query(..., description="Organization ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by name or email"),
    tag_id: Optional[int] = Query(None, description="Filter by tag ID"),
    segment: Optional[str] = Query(None, description="Filter by segment name"),
    lifecycle_stage: Optional[str] = Query(None, description="Filter by lifecycle stage"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Contact]:
    """List contacts with pagination, search, and filters."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    query = db.query(Contact).filter(Contact.organization_id == org_id)

    # Search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Contact.name.ilike(search_term)) |
            (Contact.email.ilike(search_term))
        )

    # Filter by tag
    if tag_id:
        query = query.join(Contact.tags).filter(ContactTag.id == tag_id)

    # Filter by segment
    if segment:
        query = query.filter(Contact.segment == segment)

    # Filter by lifecycle stage
    if lifecycle_stage:
        query = query.filter(Contact.lifecycle_stage == lifecycle_stage)

    contacts = query.order_by(Contact.last_seen.desc()).offset(skip).limit(limit).all()
    return contacts


@router.get("/{contact_id}", response_model=ContactDetailResponse)
async def get_contact(
    org_id: int = Query(...),
    contact_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Contact:
    """Get contact detail with conversation history."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == org_id,
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    return contact


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    org_id: int = Query(...),
    contact_data: ContactCreate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Contact:
    """Create a new contact."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Check if contact already exists
    existing = db.query(Contact).filter(
        Contact.organization_id == org_id,
        Contact.external_id == contact_data.external_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact with this external_id already exists",
        )

    # Create new contact
    new_contact = Contact(
        organization_id=org_id,
        external_id=contact_data.external_id,
        name=contact_data.name,
        email=contact_data.email,
        phone=contact_data.phone,
        avatar_url=contact_data.avatar_url,
        language=contact_data.language,
        timezone=contact_data.timezone,
        custom_fields=contact_data.custom_fields,
        segment=contact_data.segment,
        lifecycle_stage=contact_data.lifecycle_stage,
        notes=contact_data.notes,
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    org_id: int = Query(...),
    contact_id: int = None,
    contact_data: ContactUpdate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Contact:
    """Update contact information."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == org_id,
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # Update fields
    update_data = contact_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


# ============ Contact Tags ============

@router.get("/tags/list", response_model=List[ContactTagResponse])
async def list_tags(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ContactTag]:
    """List all tags for an organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    tags = db.query(ContactTag).filter(ContactTag.organization_id == org_id).all()
    return tags


@router.post("/tags", response_model=ContactTagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    org_id: int = Query(...),
    tag_data: ContactTagCreate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactTag:
    """Create a new contact tag."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Check if tag already exists
    existing = db.query(ContactTag).filter(
        ContactTag.organization_id == org_id,
        ContactTag.name == tag_data.name,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tag with this name already exists",
        )

    new_tag = ContactTag(
        organization_id=org_id,
        name=tag_data.name,
        color=tag_data.color,
    )

    db.add(new_tag)
    db.commit()
    db.refresh(new_tag)
    return new_tag


@router.post("/{contact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_tag_to_contact(
    org_id: int = Query(...),
    contact_id: int = None,
    tag_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Add a tag to a contact."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == org_id,
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    tag = db.query(ContactTag).filter(
        ContactTag.id == tag_id,
        ContactTag.organization_id == org_id,
    ).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    # Add tag if not already added
    if tag not in contact.tags:
        contact.tags.append(tag)
        db.commit()


@router.delete("/{contact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tag_from_contact(
    org_id: int = Query(...),
    contact_id: int = None,
    tag_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a tag from a contact."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.organization_id == org_id,
    ).first()

    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    tag = db.query(ContactTag).filter(
        ContactTag.id == tag_id,
        ContactTag.organization_id == org_id,
    ).first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found",
        )

    # Remove tag if present
    if tag in contact.tags:
        contact.tags.remove(tag)
        db.commit()


# ============ Segments ============

@router.get("/segments/list", response_model=List[SegmentResponse])
async def list_segments(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Segment]:
    """List all segments for an organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    segments = db.query(Segment).filter(Segment.organization_id == org_id).all()
    return segments


@router.post("/segments", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
async def create_segment(
    org_id: int = Query(...),
    segment_data: SegmentCreate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Segment:
    """Create a new segment with filter rules."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Check if segment already exists
    existing = db.query(Segment).filter(
        Segment.organization_id == org_id,
        Segment.name == segment_data.name,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment with this name already exists",
        )

    new_segment = Segment(
        organization_id=org_id,
        name=segment_data.name,
        description=segment_data.description,
        filter_config=segment_data.filter_config,
    )

    db.add(new_segment)
    db.commit()
    db.refresh(new_segment)
    return new_segment


@router.put("/segments/{segment_id}", response_model=SegmentResponse)
async def update_segment(
    org_id: int = Query(...),
    segment_id: int = None,
    segment_data: SegmentUpdate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Segment:
    """Update a segment."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    segment = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.organization_id == org_id,
    ).first()

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found",
        )

    # Update fields
    update_data = segment_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(segment, field, value)

    db.commit()
    db.refresh(segment)
    return segment


@router.delete("/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    org_id: int = Query(...),
    segment_id: int = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a segment."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    segment = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.organization_id == org_id,
    ).first()

    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found",
        )

    db.delete(segment)
    db.commit()
