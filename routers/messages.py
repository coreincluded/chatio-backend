"""Messages router for unified inbox."""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from database import SessionLocal
from models import User, Organization, Channel, Conversation, Message, MessageDirection, ChannelType
from schemas import MessageCreate, MessageResponse, ConversationResponse, ConversationListResponse, ConversationCreate, ConversationUpdate
from routers.auth import get_current_user
from services.automation_engine import process_automation_rules
from services import line, facebook, instagram, twitter, linkedin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/messages", tags=["messages"])


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


# ============ Conversation endpoints ============

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    org_id: int,
    conv_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Create a new conversation."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Verify channel belongs to org
    channel = db.query(Channel).filter(
        Channel.id == conv_data.channel_id,
        Channel.organization_id == org_id,
    ).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Check if conversation already exists
    existing_conv = db.query(Conversation).filter(
        Conversation.channel_id == conv_data.channel_id,
        Conversation.external_conversation_id == conv_data.external_conversation_id,
    ).first()
    if existing_conv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation already exists",
        )

    # Create new conversation
    new_conv = Conversation(
        organization_id=org_id,
        channel_id=conv_data.channel_id,
        external_conversation_id=conv_data.external_conversation_id,
        customer_name=conv_data.customer_name,
        customer_external_id=conv_data.customer_external_id,
        subject=conv_data.subject,
    )

    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    return new_conv


@router.get("/conversations", response_model=List[ConversationListResponse])
async def list_conversations(
    org_id: int,
    channel_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Conversation]:
    """List conversations for an organization."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    query = db.query(Conversation).filter(Conversation.organization_id == org_id)

    if channel_id:
        query = query.filter(Conversation.channel_id == channel_id)

    if active_only:
        query = query.filter(Conversation.is_active == True)

    conversations = query.order_by(desc(Conversation.last_message_at)).limit(limit).offset(offset).all()
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    org_id: int,
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Get a specific conversation with messages."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    org_id: int,
    conversation_id: int,
    conv_data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    """Update a conversation."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Update fields
    update_data = conv_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    db.commit()
    db.refresh(conversation)
    return conversation


# ============ Message endpoints ============

@router.post("/{conversation_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    org_id: int,
    conversation_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    """Send a message in a conversation."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Verify conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get channel
    channel = db.query(Channel).filter(Channel.id == conversation.channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Create outbound message record
    new_message = Message(
        conversation_id=conversation_id,
        channel_id=channel.id,
        external_message_id=f"{conversation_id}_{datetime.utcnow().timestamp()}",
        sender_id=str(current_user.id),
        sender_name=current_user.full_name or current_user.username,
        direction=MessageDirection.OUTBOUND,
        content=message_data.content,
        is_automated=False,
    )

    # Send message via appropriate service
    try:
        sent = await _send_message_via_channel(channel, conversation, message_data.content)
        if not sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send message via channel",
            )
    except Exception as e:
        logger.error(f"Error sending message via channel: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message",
        )

    db.add(new_message)
    conversation.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(new_message)

    return new_message


async def _send_message_via_channel(channel: Channel, conversation: Conversation, text: str) -> bool:
    """
    Send message via the appropriate channel service.

    Args:
        channel: The channel to send via
        conversation: The conversation context
        text: Message text to send

    Returns:
        True if message was sent successfully
    """
    try:
        if channel.channel_type == ChannelType.LINE_OA:
            client = line.LINEClient(channel)
            return await client.send_text_message(conversation.customer_external_id, text)

        elif channel.channel_type == ChannelType.FACEBOOK_MESSENGER:
            client = facebook.FacebookClient(channel)
            return await client.send_text_message(conversation.customer_external_id, text)

        elif channel.channel_type == ChannelType.INSTAGRAM_DM:
            client = instagram.InstagramClient(channel)
            return await client.send_text_message(conversation.customer_external_id, text)

        elif channel.channel_type == ChannelType.TWITTER_X:
            client = twitter.TwitterClient(channel)
            return await client.send_text_message(conversation.customer_external_id, text)

        elif channel.channel_type == ChannelType.LINKEDIN:
            client = linkedin.LinkedInClient(channel)
            return await client.send_direct_message(conversation.customer_external_id, text)

        else:
            logger.error(f"Unknown channel type: {channel.channel_type}")
            return False

    except Exception as e:
        logger.error(f"Error sending message via {channel.channel_type}: {str(e)}")
        return False


@router.get("/{conversation_id}", response_model=List[MessageResponse])
async def list_messages(
    org_id: int,
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Message]:
    """List messages in a conversation."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Verify conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
    ).order_by(desc(Message.created_at)).limit(limit).offset(offset).all()

    return messages


@router.get("/{conversation_id}/{message_id}", response_model=MessageResponse)
async def get_message(
    org_id: int,
    conversation_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    """Get a specific message."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Verify conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    message = db.query(Message).filter(
        Message.id == message_id,
        Message.conversation_id == conversation_id,
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    return message


@router.post("/{conversation_id}/process-automation", status_code=status.HTTP_200_OK)
async def process_conversation_automation(
    org_id: int,
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger automation rule processing for a conversation."""
    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Verify conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get latest inbound message
    latest_message = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.direction == MessageDirection.INBOUND,
    ).order_by(desc(Message.created_at)).first()

    if not latest_message:
        return {"status": "no_messages", "triggered_automations": []}

    # Process automations
    triggered = await process_automation_rules(
        conversation=conversation,
        message=latest_message,
        db=db,
    )

    return {
        "status": "processed",
        "triggered_automations": [auto.id for auto in triggered],
    }
