"""SQLAlchemy ORM models for Chatio."""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey,
    Enum as SQLEnum, JSON, Table, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class ChannelType(str, Enum):
    """Supported channel types."""
    LINE_OA = "line_oa"
    FACEBOOK_MESSENGER = "facebook_messenger"
    INSTAGRAM_DM = "instagram_dm"
    TWITTER_X = "twitter_x"
    LINKEDIN = "linkedin"


class AutomationTriggerType(str, Enum):
    """Types of automation triggers."""
    KEYWORD = "keyword"
    NEW_CONVERSATION = "new_conversation"
    MESSAGE_CONTAINS = "message_contains"
    INTENT = "intent"
    TIME_BASED = "time_based"


class MessageDirection(str, Enum):
    """Message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class LifecycleStage(str, Enum):
    """Customer lifecycle stages."""
    LEAD = "lead"
    CUSTOMER = "customer"
    VIP = "vip"
    CHURNED = "churned"


class AppointmentStatus(str, Enum):
    """Appointment status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TeamMemberRole(str, Enum):
    """Team member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    AGENT = "agent"
    SUPERVISOR = "supervisor"


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organizations = relationship("Organization", back_populates="owner")
    team_memberships = relationship("TeamMember", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"


class Organization(Base):
    """Organization/Business model."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    logo_url = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="organizations")
    channels = relationship("Channel", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="organization", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    team_members = relationship("TeamMember", back_populates="organization", cascade="all, delete-orphan")
    contacts = relationship("Contact", cascade="all, delete-orphan")
    segments = relationship("Segment", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="unique_org_per_owner"),
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"


class Channel(Base):
    """Connected chat channel (LINE, Facebook, Instagram)."""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    channel_type = Column(SQLEnum(ChannelType), nullable=False, index=True)
    external_channel_id = Column(String(500), nullable=False, index=True)
    access_token = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    webhook_url = Column(String(500))
    extra_data = Column(JSON, default={})  # Store channel-specific data
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="channels")
    conversations = relationship("Conversation", back_populates="channel", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organization_id", "external_channel_id", name="unique_channel_per_org"),
    )

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, type={self.channel_type}, org_id={self.organization_id})>"


class Conversation(Base):
    """Conversation thread with a customer."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    external_conversation_id = Column(String(500), nullable=False, index=True)
    customer_name = Column(String(255))
    customer_external_id = Column(String(500), nullable=False)
    subject = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    last_message_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="conversations")
    channel = relationship("Channel", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    contact = relationship("Contact", back_populates="conversations")
    assignments = relationship("ConversationAssignment", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("channel_id", "external_conversation_id", name="unique_conv_per_channel"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, channel_id={self.channel_id}, customer={self.customer_external_id})>"


class Message(Base):
    """Individual message in a conversation."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    external_message_id = Column(String(500), nullable=False, index=True)
    sender_id = Column(String(500), nullable=False)
    sender_name = Column(String(255))
    direction = Column(SQLEnum(MessageDirection), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_automated = Column(Boolean, default=False, index=True)
    automation_id = Column(Integer, ForeignKey("automations.id"), nullable=True)
    extra_data = Column(JSON, default={})  # Store message-specific data (attachments, etc.)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")
    automation = relationship("Automation", back_populates="triggered_messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conv_id={self.conversation_id}, sender={self.sender_id})>"


class Automation(Base):
    """Automation rule for handling incoming messages."""
    __tablename__ = "automations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    trigger_type = Column(SQLEnum(AutomationTriggerType), nullable=False, index=True)
    trigger_value = Column(String(500))  # keyword, regex pattern, etc.
    action_type = Column(String(100), nullable=False)  # "auto_reply", "webhook", "notification"
    action_value = Column(Text, nullable=False)  # reply message text, webhook URL, etc.
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=0)  # Higher priority runs first
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="automations")
    triggered_messages = relationship("Message", back_populates="automation")

    def __repr__(self) -> str:
        return f"<Automation(id={self.id}, name={self.name}, trigger={self.trigger_type})>"


class Subscription(Base):
    """Subscription plan for an organization."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, unique=True)
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    max_channels = Column(Integer, default=1)
    max_conversations = Column(Integer, default=100)
    max_automations = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    renewal_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="subscription")

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, org_id={self.organization_id}, tier={self.tier})>"


class ContactTag(Base):
    """Tags for organizing and categorizing contacts."""
    __tablename__ = "contact_tags"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="gray")  # Color identifier (gray, red, blue, etc.)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization")
    contacts = relationship("Contact", secondary="contact_tag_association", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="unique_tag_per_org"),
    )

    def __repr__(self) -> str:
        return f"<ContactTag(id={self.id}, name={self.name}, org_id={self.organization_id})>"


# Association table for Contact-Tag many-to-many relationship
contact_tag_association = Table(
    "contact_tag_association",
    Base.metadata,
    Column("contact_id", Integer, ForeignKey("contacts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("contact_tags.id"), primary_key=True),
)


class Contact(Base):
    """Customer contact information."""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    external_id = Column(String(500), nullable=False, index=True)
    name = Column(String(255))
    email = Column(String(255), index=True)
    phone = Column(String(50))
    avatar_url = Column(String(500))
    language = Column(String(10), default="en")
    timezone = Column(String(50))
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_messages = Column(Integer, default=0, index=True)
    tags = relationship("ContactTag", secondary=contact_tag_association, back_populates="contacts")
    custom_fields = Column(JSON, default={})  # Store custom fields as JSON
    segment = Column(String(255))  # Current segment name
    lifecycle_stage = Column(SQLEnum(LifecycleStage), default=LifecycleStage.LEAD, index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    conversations = relationship("Conversation", back_populates="contact")

    __table_args__ = (
        UniqueConstraint("organization_id", "external_id", name="unique_contact_per_org"),
    )

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name={self.name}, org_id={self.organization_id})>"


class Segment(Base):
    """Auto-segmentation rules for contacts."""
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    filter_config = Column(JSON, nullable=False)  # Rules for auto-segmentation (e.g., lifecycle_stage=customer, total_messages>5)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="unique_segment_per_org"),
    )

    def __repr__(self) -> str:
        return f"<Segment(id={self.id}, name={self.name}, org_id={self.organization_id})>"


class TeamMember(Base):
    """Team member with organization and role."""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    role = Column(SQLEnum(TeamMemberRole), default=TeamMemberRole.AGENT, nullable=False)
    invited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="team_memberships")
    organization = relationship("Organization", back_populates="team_members")
    assigned_conversations = relationship("ConversationAssignment", back_populates="assigned_user", foreign_keys="ConversationAssignment.assigned_to")

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="unique_user_per_org"),
    )

    def __repr__(self) -> str:
        return f"<TeamMember(id={self.id}, user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"


class ConversationAssignment(Base):
    """Assignment of conversations to team members."""
    __tablename__ = "conversation_assignments"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    assigned_to = Column(Integer, ForeignKey("team_members.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("team_members.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="assignments")
    assigned_user = relationship("TeamMember", back_populates="assigned_conversations", foreign_keys=[assigned_to])

    __table_args__ = (
        UniqueConstraint("conversation_id", name="unique_conversation_assignment"),
    )

    def __repr__(self) -> str:
        return f"<ConversationAssignment(id={self.id}, conv_id={self.conversation_id}, assigned_to={self.assigned_to})>"


class Integration(Base):
    """Third-party service integrations (Zapier, HubSpot, Shopify, Google Calendar)."""
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    provider = Column(String(100), nullable=False, index=True)  # zapier, hubspot, shopify, google_calendar
    config = Column(Text, nullable=False)  # JSON encrypted with API keys/tokens
    is_active = Column(Boolean, default=True, index=True)
    last_synced = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="unique_integration_per_org"),
    )

    def __repr__(self) -> str:
        return f"<Integration(id={self.id}, provider={self.provider}, org_id={self.organization_id})>"


class Appointment(Base):
    """Appointments for contacts."""
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    timezone = Column(String(50), default="UTC")
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.PENDING, index=True)
    reminder_sent = Column(Boolean, default=False)
    google_calendar_event_id = Column(String(500))  # External calendar event ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    contact = relationship("Contact")
    conversation = relationship("Conversation")

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="unique_appointment_per_org"),
    )

    def __repr__(self) -> str:
        return f"<Appointment(id={self.id}, title={self.title}, status={self.status})>"


class BusinessHours(Base):
    """Business hours configuration for appointments."""
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(String(5), nullable=False)  # HH:MM format
    close_time = Column(String(5), nullable=False)  # HH:MM format
    is_closed = Column(Boolean, default=False)  # Mark entire day as closed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")

    __table_args__ = (
        UniqueConstraint("organization_id", "day_of_week", name="unique_business_hours_per_day"),
    )

    def __repr__(self) -> str:
        return f"<BusinessHours(id={self.id}, org_id={self.organization_id}, day={self.day_of_week})>"
