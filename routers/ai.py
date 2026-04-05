"""AI-powered features router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal
from models import User, Organization, Conversation, Message, MessageDirection
from routers.auth import get_current_user
from services.ai_service import get_ai_service, MessageIntent
from services.automation_templates import (
    get_all_templates,
    get_template_by_id,
    list_categories,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
settings = get_settings()


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


def get_ai_service_instance():
    """Get configured AI service instance."""
    api_key = None
    if settings.ai_provider == "openai":
        api_key = settings.openai_api_key
    elif settings.ai_provider == "anthropic":
        api_key = settings.anthropic_api_key

    service = get_ai_service(
        api_key=api_key,
        provider=settings.ai_provider,
        model=settings.ai_model,
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured",
        )

    return service


# ============ Request/Response Models ============


class SuggestReplyRequest(BaseModel):
    """Request for reply suggestions."""
    conversation_id: int
    org_id: int


class SuggestReplyResponse(BaseModel):
    """Response with reply suggestions."""
    suggestions: List[str]


class ImproveMessageRequest(BaseModel):
    """Request to improve a message."""
    text: str
    tone: str = "professional"  # professional, casual, friendly


class ImproveMessageResponse(BaseModel):
    """Response with improved message."""
    improved_text: str


class SummarizeConversationRequest(BaseModel):
    """Request to summarize a conversation."""
    conversation_id: int
    org_id: int


class SummarizeConversationResponse(BaseModel):
    """Response with conversation summary."""
    summary: str


class DetectIntentRequest(BaseModel):
    """Request to detect message intent."""
    message_text: str


class DetectIntentResponse(BaseModel):
    """Response with detected intent."""
    intent: str


class TranslateRequest(BaseModel):
    """Request to translate text."""
    text: str
    target_language: str


class TranslateResponse(BaseModel):
    """Response with translated text."""
    translated_text: str


# ============ Endpoints ============


@router.post("/suggest-reply", response_model=SuggestReplyResponse)
async def suggest_reply(
    request: SuggestReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuggestReplyResponse:
    """Generate 3 suggested replies for a conversation."""
    # Verify org access
    org = verify_org_access(current_user, request.org_id, db)

    # Get conversation and verify access
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.organization_id == request.org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get messages for context
    messages = db.query(Message).filter(
        Message.conversation_id == request.conversation_id,
    ).order_by(Message.created_at.asc()).all()

    # Convert to conversation history format
    conversation_history = []
    for msg in messages[-10:]:  # Last 10 messages for context
        role = "user" if msg.direction == MessageDirection.INBOUND else "assistant"
        conversation_history.append({
            "role": role,
            "content": msg.content,
        })

    # Get AI service and generate suggestions
    ai_service = get_ai_service_instance()

    # Get org settings
    org_settings = {
        "tone": "professional",  # TODO: Load from org settings
    }

    # Get channel type for context
    channel = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    channel_type = channel.channel.channel_type.value if channel and channel.channel else "unknown"

    suggestions = await ai_service.suggest_reply(
        conversation_history,
        channel_type,
        org_settings,
    )

    return SuggestReplyResponse(suggestions=suggestions)


@router.post("/improve-message", response_model=ImproveMessageResponse)
async def improve_message(
    request: ImproveMessageRequest,
    current_user: User = Depends(get_current_user),
) -> ImproveMessageResponse:
    """Improve a draft message."""
    ai_service = get_ai_service_instance()

    improved = await ai_service.improve_message(
        request.text,
        request.tone,
    )

    return ImproveMessageResponse(improved_text=improved)


@router.post("/summarize", response_model=SummarizeConversationResponse)
async def summarize_conversation(
    request: SummarizeConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummarizeConversationResponse:
    """Summarize a conversation."""
    # Verify org access
    verify_org_access(current_user, request.org_id, db)

    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id,
        Conversation.organization_id == request.org_id,
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get messages
    messages = db.query(Message).filter(
        Message.conversation_id == request.conversation_id,
    ).order_by(Message.created_at.asc()).all()

    # Convert to format for summarization
    messages_data = [
        {
            "sender": msg.sender_name or "Customer" if msg.direction == MessageDirection.INBOUND else "Agent",
            "content": msg.content,
        }
        for msg in messages
    ]

    # Get AI service
    ai_service = get_ai_service_instance()

    summary = await ai_service.summarize_conversation(messages_data)

    return SummarizeConversationResponse(summary=summary)


@router.post("/detect-intent", response_model=DetectIntentResponse)
async def detect_intent(
    request: DetectIntentRequest,
    current_user: User = Depends(get_current_user),
) -> DetectIntentResponse:
    """Detect the intent of a message."""
    ai_service = get_ai_service_instance()

    intent = await ai_service.detect_intent(request.message_text)

    return DetectIntentResponse(intent=intent.value)


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    request: TranslateRequest,
    current_user: User = Depends(get_current_user),
) -> TranslateResponse:
    """Translate text to a target language."""
    ai_service = get_ai_service_instance()

    translated = await ai_service.auto_translate(
        request.text,
        request.target_language,
    )

    return TranslateResponse(translated_text=translated)


# ============ Automation Templates Endpoints ============


class AutomationTemplateResponse(BaseModel):
    """Response with automation template info."""
    id: str
    name: str
    description: str
    category: str
    trigger_type: str
    action_type: str


@router.get("/templates", response_model=List[AutomationTemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
) -> List[AutomationTemplateResponse]:
    """List all available automation templates."""
    templates = get_all_templates()
    return [
        AutomationTemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            category=t.category,
            trigger_type=t.trigger_type.value,
            action_type=t.action_type,
        )
        for t in templates
    ]


@router.get("/templates/{template_id}", response_model=AutomationTemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),
) -> AutomationTemplateResponse:
    """Get a specific template."""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return AutomationTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        trigger_type=template.trigger_type.value,
        action_type=template.action_type,
    )


@router.get("/templates/categories", response_model=List[str])
async def get_categories(
    current_user: User = Depends(get_current_user),
) -> List[str]:
    """Get list of template categories."""
    return list_categories()


@router.post("/templates/{template_id}/install")
async def install_template(
    template_id: str,
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Install a template as an active automation for the organization."""
    from models import Automation

    # Verify org access
    verify_org_access(current_user, org_id, db)

    # Get template
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Create automation from template
    automation_data = template.to_automation_dict(org_id)

    automation = Automation(
        organization_id=automation_data["organization_id"],
        name=automation_data["name"],
        description=automation_data["description"],
        trigger_type=automation_data["trigger_type"],
        trigger_value=automation_data["trigger_value"],
        action_type=automation_data["action_type"],
        action_value=automation_data["action_value"],
        is_active=automation_data["is_active"],
        priority=automation_data["priority"],
    )

    db.add(automation)
    db.commit()
    db.refresh(automation)

    return {
        "id": automation.id,
        "name": automation.name,
        "message": f"Template '{template.name}' installed successfully",
    }
