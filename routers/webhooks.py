"""Webhooks router for receiving messages from external channels."""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from sqlalchemy.orm import Session
from hashlib import sha256
import hmac
import json

from database import SessionLocal
from models import Channel, Conversation, Message, MessageDirection, ChannelType
from services.automation_engine import process_automation_rules
from services.contact_service import sync_contact_from_conversation
from services import line, facebook, instagram, twitter, linkedin
from config import get_settings

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ LINE Webhook ============

@router.post("/line/{channel_id}")
async def line_webhook(
    channel_id: int,
    request: Request,
    x_line_signature: str = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """Receive webhook from LINE Messaging API."""
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.LINE_OA,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Verify signature
        body = await request.body()
        line_client = line.LINEClient(channel)
        if not await line_client.validate_webhook_signature(body, x_line_signature or ""):
            logger.warning(f"Invalid LINE webhook signature for channel {channel_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse JSON
        body_json = json.loads(body.decode())
        events = body_json.get("events", [])

        processed_count = 0
        for event in events:
            event_type = event.get("type")

            if event_type == "message":
                processed_count += await process_line_message_event(channel, event, db)
            elif event_type == "follow":
                processed_count += await process_line_follow_event(channel, event, db)
            elif event_type == "unfollow":
                processed_count += await process_line_unfollow_event(channel, event, db)

        db.commit()
        return {"status": "ok", "processed": processed_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing LINE webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


async def process_line_message_event(channel: Channel, event: Dict[str, Any], db: Session) -> int:
    """Process LINE message event."""
    try:
        message_data = event.get("message", {})
        source = event.get("source", {})
        user_id = source.get("userId")
        group_id = source.get("groupId")
        room_id = source.get("roomId")

        # Determine conversation ID
        external_conversation_id = group_id or room_id or user_id

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == external_conversation_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=external_conversation_id,
                customer_external_id=user_id,
                customer_name=message_data.get("from", "Unknown"),
            )
            db.add(conversation)

        # Create message
        message = Message(
            conversation_id=conversation.id,
            channel_id=channel.id,
            external_message_id=event.get("message", {}).get("id", f"{user_id}_{datetime.utcnow().timestamp()}"),
            sender_id=user_id,
            sender_name=message_data.get("from", "Unknown"),
            direction=MessageDirection.INBOUND,
            content=message_data.get("text", ""),
            extra_data={"message_type": message_data.get("type", "text")},
        )
        db.add(message)

        # Update conversation last message time
        conversation.last_message_at = datetime.utcnow()

        db.flush()  # Flush to ensure message is inserted

        # Sync contact from conversation
        await sync_contact_from_conversation(conversation, db)

        # Process automations
        await process_automation_rules(conversation, message, db)

        return 1

    except Exception as e:
        logger.error(f"Error processing LINE message event: {str(e)}")
        return 0


async def process_line_follow_event(channel: Channel, event: Dict[str, Any], db: Session) -> int:
    """Process LINE follow event (new conversation)."""
    try:
        source = event.get("source", {})
        user_id = source.get("userId")

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == user_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=user_id,
                customer_external_id=user_id,
                customer_name="New User",
            )
            db.add(conversation)
            db.flush()

            # Sync contact from conversation
            await sync_contact_from_conversation(conversation, db)

            # Trigger new conversation automations
            await process_automation_rules(conversation, None, db, trigger_type="new_conversation")

        return 1

    except Exception as e:
        logger.error(f"Error processing LINE follow event: {str(e)}")
        return 0


async def process_line_unfollow_event(channel: Channel, event: Dict[str, Any], db: Session) -> int:
    """Process LINE unfollow event."""
    try:
        source = event.get("source", {})
        user_id = source.get("userId")

        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == user_id,
        ).first()

        if conversation:
            conversation.is_active = False

        return 1

    except Exception as e:
        logger.error(f"Error processing LINE unfollow event: {str(e)}")
        return 0


# ============ Facebook Webhook ============

@router.get("/facebook/{channel_id}")
async def facebook_webhook_verify(
    channel_id: int,
    hub_mode: str = Query(None),
    hub_verify_token: str = Query(None),
    hub_challenge: str = Query(None),
    db: Session = Depends(get_db),
) -> str:
    """
    Verify webhook endpoint for Facebook.
    Facebook requires GET request with verification challenge.
    """
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.FACEBOOK_MESSENGER,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Verify token
        expected_token = channel.extra_data.get("verify_token", "")
        if hub_verify_token != expected_token:
            logger.warning(f"Invalid Facebook verify token for channel {channel_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid verify token",
            )

        if hub_mode == "subscribe":
            return hub_challenge
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid hub mode",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying Facebook webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify webhook",
        )


@router.post("/facebook/{channel_id}")
async def facebook_webhook(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Receive webhook from Facebook Graph API."""
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.FACEBOOK_MESSENGER,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Parse JSON
        body_json = await request.json()
        entries = body_json.get("entry", [])

        processed_count = 0
        for entry in entries:
            messaging_list = entry.get("messaging", [])
            for messaging in messaging_list:
                if "message" in messaging:
                    processed_count += await process_facebook_message_event(channel, messaging, db)

        db.commit()
        return {"status": "ok", "processed": processed_count}

    except Exception as e:
        logger.error(f"Error processing Facebook webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


async def process_facebook_message_event(channel: Channel, messaging: Dict[str, Any], db: Session) -> int:
    """Process Facebook message event."""
    try:
        sender = messaging.get("sender", {})
        recipient = messaging.get("recipient", {})
        message_data = messaging.get("message", {})

        sender_id = sender.get("id")
        external_conversation_id = sender_id

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == external_conversation_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=external_conversation_id,
                customer_external_id=sender_id,
                customer_name=f"User {sender_id}",
            )
            db.add(conversation)

        # Create message
        message = Message(
            conversation_id=conversation.id,
            channel_id=channel.id,
            external_message_id=message_data.get("mid", f"{sender_id}_{datetime.utcnow().timestamp()}"),
            sender_id=sender_id,
            sender_name=f"User {sender_id}",
            direction=MessageDirection.INBOUND,
            content=message_data.get("text", ""),
            extra_data={"has_attachments": "attachments" in message_data},
        )
        db.add(message)

        # Update conversation
        conversation.last_message_at = datetime.utcnow()

        db.flush()

        # Sync contact from conversation
        await sync_contact_from_conversation(conversation, db)

        # Process automations
        await process_automation_rules(conversation, message, db)

        return 1

    except Exception as e:
        logger.error(f"Error processing Facebook message event: {str(e)}")
        return 0


# ============ Instagram Webhook ============

@router.post("/instagram/{channel_id}")
async def instagram_webhook(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Receive webhook from Instagram Graph API."""
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.INSTAGRAM_DM,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Parse JSON
        body_json = await request.json()
        entries = body_json.get("entry", [])

        processed_count = 0
        for entry in entries:
            messaging_list = entry.get("messaging", [])
            for messaging in messaging_list:
                if "message" in messaging:
                    processed_count += await process_instagram_message_event(channel, messaging, db)

        db.commit()
        return {"status": "ok", "processed": processed_count}

    except Exception as e:
        logger.error(f"Error processing Instagram webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


async def process_instagram_message_event(channel: Channel, messaging: Dict[str, Any], db: Session) -> int:
    """Process Instagram message event."""
    try:
        sender = messaging.get("sender", {})
        message_data = messaging.get("message", {})

        sender_id = sender.get("id")
        external_conversation_id = sender_id

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == external_conversation_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=external_conversation_id,
                customer_external_id=sender_id,
                customer_name=f"User {sender_id}",
            )
            db.add(conversation)

        # Create message
        message = Message(
            conversation_id=conversation.id,
            channel_id=channel.id,
            external_message_id=message_data.get("mid", f"{sender_id}_{datetime.utcnow().timestamp()}"),
            sender_id=sender_id,
            sender_name=f"User {sender_id}",
            direction=MessageDirection.INBOUND,
            content=message_data.get("text", ""),
        )
        db.add(message)

        # Update conversation
        conversation.last_message_at = datetime.utcnow()

        db.flush()

        # Sync contact from conversation
        await sync_contact_from_conversation(conversation, db)

        # Process automations
        await process_automation_rules(conversation, message, db)

        return 1

    except Exception as e:
        logger.error(f"Error processing Instagram message event: {str(e)}")
        return 0


# ============ Twitter/X Webhook ============

@router.post("/twitter/{channel_id}")
async def twitter_webhook(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Receive webhook from Twitter/X Account Activity API.
    """
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.TWITTER_X,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Verify signature (optional, as Twitter uses bearer token)
        body = await request.body()
        x_signature = request.headers.get("x-twitter-webhooks-signature-256", "")

        twitter_client = twitter.TwitterClient(channel)
        if x_signature and not await twitter_client.validate_webhook_signature(body, x_signature):
            logger.warning(f"Invalid Twitter webhook signature for channel {channel_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        # Parse JSON
        body_json = json.loads(body.decode())

        # Handle CRC challenge (Twitter sends this during setup)
        if "for_user_id" in body_json and "crc_token" in body_json:
            # This is a CRC challenge - just return success
            logger.info(f"Twitter CRC challenge received for channel {channel_id}")
            return {"status": "ok"}

        # Process direct message events
        if "direct_message_events" in body_json:
            processed_count = 0
            for event in body_json.get("direct_message_events", []):
                processed_count += await process_twitter_message_event(channel, event, db)
            db.commit()
            return {"status": "ok", "processed": processed_count}

        return {"status": "ok", "processed": 0}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Twitter webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


async def process_twitter_message_event(channel: Channel, event: Dict[str, Any], db: Session) -> int:
    """Process Twitter direct message event."""
    try:
        # Skip message_create events we sent
        if event.get("type") != "message_create":
            return 0

        message_create = event.get("message_create", {})
        sender_id = message_create.get("sender_id")
        recipient_id = message_create.get("target", {}).get("recipient_id")
        message_data = message_create.get("message_data", {})

        # Only process if we are the recipient (messages sent to us)
        if recipient_id != channel.external_channel_id:
            return 0

        external_conversation_id = sender_id
        text = message_data.get("text", "")

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == external_conversation_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=external_conversation_id,
                customer_external_id=sender_id,
                customer_name=f"User {sender_id}",
            )
            db.add(conversation)

        # Create message
        message = Message(
            conversation_id=conversation.id,
            channel_id=channel.id,
            external_message_id=event.get("id", f"{sender_id}_{datetime.utcnow().timestamp()}"),
            sender_id=sender_id,
            sender_name=f"User {sender_id}",
            direction=MessageDirection.INBOUND,
            content=text,
        )
        db.add(message)

        # Update conversation
        conversation.last_message_at = datetime.utcnow()

        db.flush()

        # Sync contact from conversation
        await sync_contact_from_conversation(conversation, db)

        # Process automations
        await process_automation_rules(conversation, message, db)

        return 1

    except Exception as e:
        logger.error(f"Error processing Twitter message event: {str(e)}")
        return 0


# ============ LinkedIn Webhook ============

@router.post("/linkedin/{channel_id}")
async def linkedin_webhook(
    channel_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Receive webhook from LinkedIn Messaging.
    """
    try:
        # Get channel
        channel = db.query(Channel).filter(
            Channel.id == channel_id,
            Channel.channel_type == ChannelType.LINKEDIN,
        ).first()

        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found",
            )

        # Parse JSON
        body_json = await request.json()

        # LinkedIn sends events in different formats
        processed_count = 0

        # Handle messaging events
        if "data" in body_json and isinstance(body_json["data"], list):
            for event_item in body_json["data"]:
                if "elements" in event_item:
                    for element in event_item["elements"]:
                        processed_count += await process_linkedin_message_event(channel, element, db)

        db.commit()
        return {"status": "ok", "processed": processed_count}

    except Exception as e:
        logger.error(f"Error processing LinkedIn webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


async def process_linkedin_message_event(channel: Channel, event: Dict[str, Any], db: Session) -> int:
    """Process LinkedIn message event."""
    try:
        # Extract message info from LinkedIn event
        # LinkedIn's format is different - extract essentials
        message_text = event.get("text", event.get("content", ""))
        sender_id = event.get("from", {}).get("id") or event.get("from_id")
        message_id = event.get("id", f"linkedin_{datetime.utcnow().timestamp()}")

        if not sender_id or not message_text:
            return 0

        external_conversation_id = sender_id

        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.channel_id == channel.id,
            Conversation.external_conversation_id == external_conversation_id,
        ).first()

        if not conversation:
            conversation = Conversation(
                organization_id=channel.organization_id,
                channel_id=channel.id,
                external_conversation_id=external_conversation_id,
                customer_external_id=sender_id,
                customer_name=f"User {sender_id}",
            )
            db.add(conversation)

        # Create message
        message = Message(
            conversation_id=conversation.id,
            channel_id=channel.id,
            external_message_id=message_id,
            sender_id=sender_id,
            sender_name=f"User {sender_id}",
            direction=MessageDirection.INBOUND,
            content=message_text,
        )
        db.add(message)

        # Update conversation
        conversation.last_message_at = datetime.utcnow()

        db.flush()

        # Sync contact from conversation
        await sync_contact_from_conversation(conversation, db)

        # Process automations
        await process_automation_rules(conversation, message, db)

        return 1

    except Exception as e:
        logger.error(f"Error processing LinkedIn message event: {str(e)}")
        return 0


@router.get("/health")
async def webhook_health() -> dict:
    """Health check endpoint for webhooks."""
    return {"status": "ok"}
