"""Automation rule engine for processing incoming messages."""
import re
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models import Automation, AutomationTriggerType, Conversation, Message, MessageDirection
from config import get_settings

logger = logging.getLogger(__name__)


async def process_automation_rules(
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
    trigger_type: Optional[str] = None,
) -> List[Automation]:
    """
    Process automation rules for a message/conversation.

    Args:
        conversation: The conversation being processed
        message: The message that triggered the automation (may be None for new_conversation)
        db: Database session
        trigger_type: Force a specific trigger type (e.g., "new_conversation")

    Returns:
        List of automations that were triggered
    """
    triggered_automations: List[Automation] = []

    try:
        # Get all active automations for the organization
        automations = db.query(Automation).filter(
            Automation.organization_id == conversation.organization_id,
            Automation.is_active == True,
        ).order_by(
            Automation.priority.desc(),
            Automation.created_at.asc(),
        ).all()

        # Determine which trigger type to use
        if trigger_type == "new_conversation":
            # New conversation trigger
            for automation in automations:
                if automation.trigger_type == AutomationTriggerType.NEW_CONVERSATION:
                    if await execute_automation(automation, conversation, None, db):
                        triggered_automations.append(automation)

        elif message and message.direction == MessageDirection.INBOUND:
            # Message-based triggers
            for automation in automations:
                should_trigger = False

                if automation.trigger_type == AutomationTriggerType.KEYWORD:
                    # Check if message contains keyword
                    if automation.trigger_value and automation.trigger_value.lower() in message.content.lower():
                        should_trigger = True

                elif automation.trigger_type == AutomationTriggerType.MESSAGE_CONTAINS:
                    # Check if message matches regex pattern
                    if automation.trigger_value:
                        try:
                            pattern = re.compile(automation.trigger_value, re.IGNORECASE)
                            if pattern.search(message.content):
                                should_trigger = True
                        except re.error:
                            logger.error(f"Invalid regex pattern in automation {automation.id}: {automation.trigger_value}")

                # Check for intent-based trigger (AI-powered)
                if not should_trigger and automation.trigger_type.value == "intent":
                    try:
                        intent = await detect_message_intent(message.content)
                        if automation.trigger_value and automation.trigger_value.lower() == intent.lower():
                            should_trigger = True
                    except Exception as e:
                        logger.warning(f"Could not detect intent for automation: {str(e)}")

                if should_trigger:
                    if await execute_automation(automation, conversation, message, db):
                        triggered_automations.append(automation)

        return triggered_automations

    except Exception as e:
        logger.error(f"Error processing automation rules: {str(e)}")
        return triggered_automations


async def execute_automation(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute an automation rule.

    Args:
        automation: The automation to execute
        conversation: The conversation context
        message: The triggering message (may be None)
        db: Database session

    Returns:
        True if execution was successful, False otherwise
    """
    try:
        if automation.action_type == "auto_reply":
            return await execute_auto_reply(automation, conversation, message, db)

        elif automation.action_type == "webhook":
            return await execute_webhook_action(automation, conversation, message, db)

        elif automation.action_type == "notification":
            return await execute_notification_action(automation, conversation, message, db)

        elif automation.action_type == "escalate":
            return await execute_escalation_action(automation, conversation, message, db)

        elif automation.action_type == "ai_reply":
            return await execute_ai_reply_action(automation, conversation, message, db)

        else:
            logger.warning(f"Unknown action type: {automation.action_type}")
            return False

    except Exception as e:
        logger.error(f"Error executing automation {automation.id}: {str(e)}")
        return False


async def execute_auto_reply(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute auto-reply action.

    Args:
        automation: The automation with reply text
        conversation: The conversation context
        message: The triggering message
        db: Database session

    Returns:
        True if reply was created successfully
    """
    try:
        # Create outbound message record
        reply_message = Message(
            conversation_id=conversation.id,
            channel_id=conversation.channel_id,
            external_message_id=f"auto_{conversation.id}_{datetime.utcnow().timestamp()}",
            sender_id="system",
            sender_name="Automation",
            direction=MessageDirection.OUTBOUND,
            content=automation.action_value,
            is_automated=True,
            automation_id=automation.id,
        )

        db.add(reply_message)

        # Update conversation timestamp
        conversation.last_message_at = datetime.utcnow()

        db.commit()

        # Attempt to send the reply via the channel
        # Note: This is done asynchronously and may fail without breaking the automation record
        try:
            await send_reply_via_channel(conversation, automation.action_value)
        except Exception as send_err:
            logger.warning(f"Failed to send auto-reply via channel: {str(send_err)}")
            # We still consider it a success since the message was recorded

        logger.info(f"Auto-reply sent for automation {automation.id} in conversation {conversation.id}")
        return True

    except Exception as e:
        logger.error(f"Error executing auto-reply: {str(e)}")
        db.rollback()
        return False


async def send_reply_via_channel(conversation: Conversation, text: str) -> bool:
    """
    Send an auto-reply via the channel.

    Args:
        conversation: The conversation to send to
        text: Reply text

    Returns:
        True if message was sent successfully
    """
    try:
        from models import Channel, ChannelType
        from sqlalchemy.orm import sessionmaker
        from database import engine

        # Create a new session for this operation
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            # Get channel
            channel = db.query(Channel).filter(
                Channel.id == conversation.channel_id,
            ).first()

            if not channel:
                logger.error(f"Channel not found for conversation {conversation.id}")
                return False

            # Import service clients
            from services import line, facebook, instagram, twitter, linkedin

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

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error sending reply via channel: {str(e)}")
        return False


async def execute_webhook_action(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute webhook action (call external URL).

    Args:
        automation: The automation with webhook URL
        conversation: The conversation context
        message: The triggering message
        db: Database session

    Returns:
        True if webhook was called successfully
    """
    try:
        import httpx

        webhook_url = automation.action_value
        payload = {
            "automation_id": automation.id,
            "conversation_id": conversation.id,
            "organization_id": conversation.organization_id,
            "customer_id": conversation.customer_external_id,
            "customer_name": conversation.customer_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if message:
            payload.update({
                "message_id": message.id,
                "message_content": message.content,
                "message_direction": message.direction.value,
            })

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()

        logger.info(f"Webhook action executed for automation {automation.id}")
        return True

    except Exception as e:
        logger.error(f"Error executing webhook action: {str(e)}")
        return False


async def execute_notification_action(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute notification action (log notification).

    Args:
        automation: The automation
        conversation: The conversation context
        message: The triggering message
        db: Database session

    Returns:
        True if notification was logged
    """
    try:
        notification_text = automation.action_value
        logger.info(
            f"Automation notification: {notification_text} "
            f"(conv={conversation.id}, customer={conversation.customer_external_id})"
        )
        return True

    except Exception as e:
        logger.error(f"Error executing notification action: {str(e)}")
        return False


async def execute_escalation_action(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute escalation action (mark conversation for human review).

    Args:
        automation: The automation
        conversation: The conversation context
        message: The triggering message
        db: Database session

    Returns:
        True if escalation was recorded
    """
    try:
        # Mark conversation as needing escalation (could use a flag or tag)
        # For now, log it and optionally create a notification message
        logger.info(
            f"Conversation {conversation.id} escalated by automation {automation.id}. "
            f"Reason: {automation.action_value}"
        )

        # Optionally add a system message to the conversation
        if automation.action_value:
            system_message = Message(
                conversation_id=conversation.id,
                channel_id=conversation.channel_id,
                external_message_id=f"escalation_{conversation.id}_{datetime.utcnow().timestamp()}",
                sender_id="system",
                sender_name="Automation",
                direction=MessageDirection.OUTBOUND,
                content=automation.action_value,
                is_automated=True,
                automation_id=automation.id,
            )
            db.add(system_message)

        db.commit()
        return True

    except Exception as e:
        logger.error(f"Error executing escalation action: {str(e)}")
        db.rollback()
        return False


async def execute_ai_reply_action(
    automation: Automation,
    conversation: Conversation,
    message: Optional[Message],
    db: Session,
) -> bool:
    """
    Execute AI-generated reply action.

    Args:
        automation: The automation
        conversation: The conversation context
        message: The triggering message
        db: Database session

    Returns:
        True if AI reply was generated and sent
    """
    try:
        from services.ai_service import get_ai_service

        settings = get_settings()
        api_key = None
        if settings.ai_provider == "openai":
            api_key = settings.openai_api_key
        elif settings.ai_provider == "anthropic":
            api_key = settings.anthropic_api_key

        ai_service = get_ai_service(api_key, settings.ai_provider, settings.ai_model)
        if not ai_service:
            logger.warning("AI service not configured for AI reply automation")
            return False

        # Get recent messages for context
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id,
        ).order_by(Message.created_at.asc()).all()[-5:]

        conversation_history = [
            {
                "role": "user" if msg.direction == MessageDirection.INBOUND else "assistant",
                "content": msg.content,
            }
            for msg in recent_messages
        ]

        # Generate reply using AI
        suggestions = await ai_service.suggest_reply(
            conversation_history,
            conversation.channel.channel_type.value,
            {},
        )

        if not suggestions:
            logger.warning(f"No AI reply generated for automation {automation.id}")
            return False

        # Use the first suggestion
        reply_text = suggestions[0]

        # Create outbound message
        reply_message = Message(
            conversation_id=conversation.id,
            channel_id=conversation.channel_id,
            external_message_id=f"ai_reply_{conversation.id}_{datetime.utcnow().timestamp()}",
            sender_id="system",
            sender_name="AI Assistant",
            direction=MessageDirection.OUTBOUND,
            content=reply_text,
            is_automated=True,
            automation_id=automation.id,
        )

        db.add(reply_message)
        conversation.last_message_at = datetime.utcnow()
        db.commit()

        # Attempt to send via channel
        try:
            await send_reply_via_channel(conversation, reply_text)
        except Exception as send_err:
            logger.warning(f"Failed to send AI reply via channel: {str(send_err)}")

        logger.info(f"AI reply sent for automation {automation.id} in conversation {conversation.id}")
        return True

    except Exception as e:
        logger.error(f"Error executing AI reply action: {str(e)}")
        db.rollback()
        return False


async def detect_message_intent(message_text: str) -> str:
    """
    Detect intent of a message using AI.

    Args:
        message_text: The message to analyze

    Returns:
        Intent classification
    """
    try:
        from services.ai_service import get_ai_service

        settings = get_settings()
        api_key = None
        if settings.ai_provider == "openai":
            api_key = settings.openai_api_key
        elif settings.ai_provider == "anthropic":
            api_key = settings.anthropic_api_key

        ai_service = get_ai_service(api_key, settings.ai_provider, settings.ai_model)
        if not ai_service:
            return "unknown"

        intent = await ai_service.detect_intent(message_text)
        return intent.value

    except Exception as e:
        logger.warning(f"Could not detect intent: {str(e)}")
        return "unknown"
