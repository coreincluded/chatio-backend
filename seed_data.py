"""Seed script to create org and demo data for test user."""
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import (
    User, Organization, Channel, Conversation, Message,
    Automation, Subscription, ChannelType, MessageDirection,
    AutomationTriggerType, SubscriptionTier
)


def seed_database():
    """Seed database with test user org and demo data."""
    # Initialize DB tables if they don't exist
    init_db()

    db = SessionLocal()
    try:
        # Find or create test user
        test_user = db.query(User).filter(User.email == "test@chatio.com").first()
        if not test_user:
            print("Test user not found. Creating...")
            test_user = User(
                email="test@chatio.com",
                username="testuser",
                full_name="Test User",
                hashed_password="$2b$12$mock_hash_for_testing"
            )
            db.add(test_user)
            db.commit()
            db.refresh(test_user)
            print(f"Created test user with id={test_user.id}")
        else:
            print(f"Found existing test user with id={test_user.id}")

        # Check if organization already exists for this user
        existing_org = db.query(Organization).filter(
            Organization.owner_id == test_user.id,
            Organization.name == "Test Organization"
        ).first()
        if existing_org:
            print(f"Organization already exists (id={existing_org.id}). Skipping creation.")
            db.close()
            return

        # Create organization (id should be 1 to match frontend hardcoded value)
        org = Organization(
            owner_id=test_user.id,
            name="Test Organization",
            description="Test organization for demo",
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"Created organization with id={org.id}")

        # Create channels (LINE, Facebook Messenger, Instagram DM)
        channels_data = [
            {
                "name": "LINE Official Account",
                "channel_type": ChannelType.LINE_OA,
                "external_channel_id": "U1234567890abcdef1234567890abcdef",
                "access_token": "mock_line_token_123456789"
            },
            {
                "name": "Facebook Messenger",
                "channel_type": ChannelType.FACEBOOK_MESSENGER,
                "external_channel_id": "page_id_1234567890",
                "access_token": "mock_fb_token_abc123def456"
            },
            {
                "name": "Instagram DM",
                "channel_type": ChannelType.INSTAGRAM_DM,
                "external_channel_id": "ig_business_account_789",
                "access_token": "mock_ig_token_xyz789"
            },
        ]

        channels = []
        for ch_data in channels_data:
            channel = Channel(
                organization_id=org.id,
                name=ch_data["name"],
                channel_type=ch_data["channel_type"],
                external_channel_id=ch_data["external_channel_id"],
                access_token=ch_data["access_token"],
            )
            db.add(channel)
            db.commit()
            db.refresh(channel)
            channels.append(channel)
            print(f"Created channel: {channel.name} (id={channel.id})")

        # Create conversations with messages
        conversations = []
        base_time = datetime.utcnow()

        for i, channel in enumerate(channels):
            for j in range(2):
                conv = Conversation(
                    organization_id=org.id,
                    channel_id=channel.id,
                    external_conversation_id=f"{channel.external_channel_id}_conv_{j}",
                    customer_name=f"Customer {i*2 + j + 1}",
                    customer_external_id=f"customer_ext_id_{i*2 + j}",
                    subject=f"Inquiry about product {i*2 + j + 1}",
                    last_message_at=base_time - timedelta(hours=i*2 + j),
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)
                conversations.append(conv)

                # Add 2-3 messages to each conversation
                for k in range(2 + (j % 2)):
                    direction = MessageDirection.INBOUND if k % 2 == 0 else MessageDirection.OUTBOUND
                    msg = Message(
                        conversation_id=conv.id,
                        channel_id=channel.id,
                        external_message_id=f"msg_ext_{i}_{j}_{k}",
                        sender_id=f"sender_{i}_{j}" if direction == MessageDirection.INBOUND else "bot_agent",
                        sender_name=f"Customer {i*2 + j + 1}" if direction == MessageDirection.INBOUND else "Support Bot",
                        direction=direction,
                        content=f"Message {k+1}: {'Customer inquiry' if direction == MessageDirection.INBOUND else 'Automated response'}" +
                                f" about product features and pricing.",
                        created_at=base_time - timedelta(hours=i*2 + j) + timedelta(minutes=k*10),
                    )
                    db.add(msg)

                db.commit()
                print(f"Created conversation (id={conv.id}) with {2 + (j % 2)} messages")

        # Create automations
        automations_data = [
            {
                "name": "Welcome Message",
                "description": "Auto-reply with welcome message for new conversations",
                "trigger_type": AutomationTriggerType.NEW_CONVERSATION,
                "trigger_value": None,
                "action_type": "auto_reply",
                "action_value": "Thank you for contacting us! We'll respond shortly.",
            },
            {
                "name": "Keyword: Price",
                "description": "Auto-reply when customer mentions 'price'",
                "trigger_type": AutomationTriggerType.MESSAGE_CONTAINS,
                "trigger_value": "price",
                "action_type": "auto_reply",
                "action_value": "Our pricing varies by plan. Please visit our pricing page for details.",
            },
        ]

        for auto_data in automations_data:
            automation = Automation(
                organization_id=org.id,
                name=auto_data["name"],
                description=auto_data["description"],
                trigger_type=auto_data["trigger_type"],
                trigger_value=auto_data["trigger_value"],
                action_type=auto_data["action_type"],
                action_value=auto_data["action_value"],
                priority=0,
            )
            db.add(automation)
            db.commit()
            db.refresh(automation)
            print(f"Created automation: {automation.name} (id={automation.id})")

        # Create subscription
        subscription = Subscription(
            organization_id=org.id,
            tier=SubscriptionTier.FREE,
            max_channels=1,
            max_conversations=100,
            max_automations=5,
            renewal_date=base_time + timedelta(days=30),
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        print(f"Created subscription (id={subscription.id}) with tier={subscription.tier}")

        print("\n✓ Seed data created successfully!")

    except Exception as e:
        print(f"Error seeding database: {e}", file=sys.stderr)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
