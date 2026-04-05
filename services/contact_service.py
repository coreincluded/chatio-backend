"""Contact service for managing customer intelligence."""
from datetime import datetime
from sqlalchemy.orm import Session
from models import Contact, Conversation, Message, Organization


async def get_or_create_contact(
    conversation: Conversation,
    db: Session,
) -> Contact:
    """Get existing contact or create a new one from conversation."""
    # Try to find existing contact with same external_id
    contact = db.query(Contact).filter(
        Contact.organization_id == conversation.organization_id,
        Contact.external_id == conversation.customer_external_id,
    ).first()

    if contact:
        return contact

    # Create new contact from conversation
    contact = Contact(
        organization_id=conversation.organization_id,
        external_id=conversation.customer_external_id,
        name=conversation.customer_name or f"User {conversation.customer_external_id}",
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
    )

    db.add(contact)
    db.flush()
    return contact


async def update_contact_metrics(
    conversation: Conversation,
    db: Session,
) -> None:
    """Update contact metrics based on conversation."""
    if not conversation.contact_id:
        # Link conversation to contact
        contact = await get_or_create_contact(conversation, db)
        conversation.contact_id = contact.id
    else:
        contact = db.query(Contact).filter(Contact.id == conversation.contact_id).first()
        if not contact:
            return

    # Update contact metrics
    contact.last_seen = datetime.utcnow()

    # Count messages in this conversation
    message_count = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).count()

    # Update total messages across all conversations
    total_messages = db.query(Message).join(
        Conversation, Message.conversation_id == Conversation.id
    ).filter(
        Conversation.contact_id == contact.id
    ).count()

    contact.total_messages = total_messages

    db.flush()


async def sync_contact_from_conversation(
    conversation: Conversation,
    db: Session,
) -> Contact:
    """
    Sync contact information from conversation.
    This is called when a webhook creates/updates a conversation.
    """
    contact = await get_or_create_contact(conversation, db)

    # Link conversation to contact
    conversation.contact_id = contact.id

    # Update contact metrics
    await update_contact_metrics(conversation, db)

    return contact
