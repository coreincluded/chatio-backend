"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


# Enums
class ChannelType(str, Enum):
    """Supported channel types."""
    LINE_OA = "line_oa"
    FACEBOOK_MESSENGER = "facebook_messenger"
    INSTAGRAM_DM = "instagram_dm"
    TWITTER_X = "twitter_x"
    LINKEDIN = "linkedin"


class MessageDirection(str, Enum):
    """Message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class AutomationTriggerType(str, Enum):
    """Types of automation triggers."""
    KEYWORD = "keyword"
    NEW_CONVERSATION = "new_conversation"
    MESSAGE_CONTAINS = "message_contains"
    INTENT = "intent"
    TIME_BASED = "time_based"


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


# User schemas
class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str


class LoginRequest(BaseModel):
    """Schema for login - only email and password needed."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    full_name: Optional[str] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    """User response schema."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Token schemas
class Token(BaseModel):
    """JWT token schema."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    org_id: Optional[int] = None


# Organization schemas
class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""
    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Channel schemas
class ChannelBase(BaseModel):
    """Base channel schema."""
    name: str
    channel_type: ChannelType
    external_channel_id: str
    access_token: str


class ChannelCreate(ChannelBase):
    """Schema for creating a channel."""
    pass


class ChannelUpdate(BaseModel):
    """Schema for updating a channel."""
    name: Optional[str] = None
    access_token: Optional[str] = None
    is_active: Optional[bool] = None
    webhook_url: Optional[str] = None


class ChannelResponse(ChannelBase):
    """Channel response schema."""
    id: int
    organization_id: int
    is_active: bool
    webhook_url: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Message schemas
class MessageBase(BaseModel):
    """Base message schema."""
    content: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None


class MessageCreate(MessageBase):
    """Schema for creating a message."""
    conversation_id: int


class MessageResponse(MessageBase):
    """Message response schema."""
    id: int
    conversation_id: int
    channel_id: int
    external_message_id: str
    direction: MessageDirection
    is_automated: bool
    automation_id: Optional[int] = None
    extra_data: dict = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


# Conversation schemas
class ConversationBase(BaseModel):
    """Base conversation schema."""
    customer_name: Optional[str] = None
    customer_external_id: str
    subject: Optional[str] = None


class ConversationCreate(ConversationBase):
    """Schema for creating a conversation."""
    channel_id: int
    external_conversation_id: str


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""
    subject: Optional[str] = None
    is_active: Optional[bool] = None


class ConversationResponse(ConversationBase):
    """Conversation response schema."""
    id: int
    organization_id: int
    channel_id: int
    external_conversation_id: str
    is_active: bool
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Conversation list response (without messages)."""
    id: int
    customer_name: Optional[str]
    customer_external_id: str
    subject: Optional[str]
    is_active: bool
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Automation schemas
class AutomationBase(BaseModel):
    """Base automation schema."""
    name: str
    description: Optional[str] = None
    trigger_type: AutomationTriggerType
    trigger_value: Optional[str] = None
    action_type: str
    action_value: str
    priority: int = 0


class AutomationCreate(AutomationBase):
    """Schema for creating an automation."""
    pass


class AutomationUpdate(BaseModel):
    """Schema for updating an automation."""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[AutomationTriggerType] = None
    trigger_value: Optional[str] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class AutomationResponse(AutomationBase):
    """Automation response schema."""
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Subscription schemas
class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    tier: SubscriptionTier
    max_channels: int = 1
    max_conversations: int = 100
    max_automations: int = 5


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a subscription."""
    pass


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription."""
    tier: Optional[SubscriptionTier] = None
    max_channels: Optional[int] = None
    max_conversations: Optional[int] = None
    max_automations: Optional[int] = None
    is_active: Optional[bool] = None


class SubscriptionResponse(SubscriptionBase):
    """Subscription response schema."""
    id: int
    organization_id: int
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    is_active: bool
    started_at: datetime
    renewal_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Error schemas
class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    status_code: int


# Webhook schemas
class LineWebhookEvent(BaseModel):
    """LINE webhook event schema."""
    events: List[dict]
    destination: str


class FacebookWebhookEvent(BaseModel):
    """Facebook webhook event schema."""
    object: str
    entry: List[dict]


class InstagramWebhookEvent(BaseModel):
    """Instagram webhook event schema."""
    object: str
    entry: List[dict]


# Contact-related schemas
class ContactTagBase(BaseModel):
    """Base contact tag schema."""
    name: str
    color: str = "gray"


class ContactTagCreate(ContactTagBase):
    """Schema for creating a contact tag."""
    pass


class ContactTagResponse(ContactTagBase):
    """Contact tag response schema."""
    id: int
    organization_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ContactBase(BaseModel):
    """Base contact schema."""
    external_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    language: str = "en"
    timezone: Optional[str] = None
    custom_fields: dict = Field(default_factory=dict)
    segment: Optional[str] = None
    lifecycle_stage: LifecycleStage = LifecycleStage.LEAD
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    """Schema for creating a contact."""
    pass


class ContactUpdate(BaseModel):
    """Schema for updating a contact."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    custom_fields: Optional[dict] = None
    segment: Optional[str] = None
    lifecycle_stage: Optional[LifecycleStage] = None
    notes: Optional[str] = None


class ContactResponse(ContactBase):
    """Contact response schema."""
    id: int
    organization_id: int
    first_seen: datetime
    last_seen: datetime
    total_messages: int
    tags: List[ContactTagResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactDetailResponse(ContactResponse):
    """Detailed contact response with conversation history."""
    conversations: List["ConversationListResponse"] = []


# Segment schemas
class SegmentBase(BaseModel):
    """Base segment schema."""
    name: str
    description: Optional[str] = None
    filter_config: dict


class SegmentCreate(SegmentBase):
    """Schema for creating a segment."""
    pass


class SegmentUpdate(BaseModel):
    """Schema for updating a segment."""
    name: Optional[str] = None
    description: Optional[str] = None
    filter_config: Optional[dict] = None


class SegmentResponse(SegmentBase):
    """Segment response schema."""
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Integration schemas
class IntegrationConfig(BaseModel):
    """Configuration for an integration."""
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    shop_domain: Optional[str] = None


class IntegrationResponse(BaseModel):
    """Integration response schema."""
    id: int
    organization_id: int
    provider: str
    is_active: bool
    last_synced: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Appointment schemas
class AppointmentCreate(BaseModel):
    """Schema for creating an appointment."""
    contact_id: Optional[int] = None
    conversation_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: Optional[str] = "UTC"
    status: Optional[AppointmentStatus] = AppointmentStatus.PENDING


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: Optional[str] = None
    status: Optional[AppointmentStatus] = None
    reminder_sent: Optional[bool] = None
    google_calendar_event_id: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Appointment response schema."""
    id: int
    organization_id: int
    contact_id: Optional[int] = None
    conversation_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    timezone: str
    status: AppointmentStatus
    reminder_sent: bool
    google_calendar_event_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BusinessHoursCreate(BaseModel):
    """Schema for creating business hours."""
    day_of_week: int  # 0=Monday, 6=Sunday
    open_time: str  # HH:MM format
    close_time: str  # HH:MM format
    is_closed: bool = False


class BusinessHoursUpdate(BaseModel):
    """Schema for updating business hours."""
    day_of_week: int
    open_time: str
    close_time: str
    is_closed: Optional[bool] = False


class BusinessHoursResponse(BaseModel):
    """Business hours response schema."""
    id: int
    organization_id: int
    day_of_week: int
    open_time: str
    close_time: str
    is_closed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailableSlotsRequest(BaseModel):
    """Request for available appointment slots."""
    date: str  # YYYY-MM-DD
    duration_minutes: int = 30
    timezone: str = "UTC"


# Translation schemas
class TranslateRequest(BaseModel):
    """Schema for translation request."""
    text: str
    target_language: str  # Language code (en, ja, zh-tw, etc.) or name
    source_language: Optional[str] = "auto"


class TranslateResponse(BaseModel):
    """Schema for translation response."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


class DetectLanguageRequest(BaseModel):
    """Schema for language detection request."""
    text: str


class TranslationSettings(BaseModel):
    """Schema for translation settings."""
    auto_translate_incoming: bool = False
    auto_translate_outgoing: bool = False
    default_language: str = "en"
    supported_languages: List[str] = ["en", "ja", "zh-tw"]


# Integration schemas
class IntegrationConfig(BaseModel):
    """Schema for integration configuration."""
    provider: str
    config: dict = Field(default_factory=dict)


class IntegrationCreate(BaseModel):
    """Schema for creating an integration."""
    provider: str
    config: dict


class IntegrationResponse(BaseModel):
    """Schema for integration response."""
    id: int
    organization_id: int
    provider: str
    config: dict
    is_active: bool
    last_synced: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Password reset schemas
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
