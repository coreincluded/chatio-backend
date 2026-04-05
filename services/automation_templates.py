"""Pre-built automation templates for common use cases."""
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TriggerType(str, Enum):
    """Automation trigger types."""
    KEYWORD = "keyword"
    NEW_CONVERSATION = "new_conversation"
    MESSAGE_CONTAINS = "message_contains"
    INTENT = "intent"
    TIME_BASED = "time_based"


@dataclass
class AutomationTemplate:
    """Represents an automation template."""
    id: str
    name: str
    description: str
    category: str
    trigger_type: TriggerType
    trigger_config: Dict[str, Any]
    action_type: str
    action_config: Dict[str, Any]
    is_active: bool = True
    priority: int = 0

    def to_automation_dict(self, org_id: int) -> Dict[str, Any]:
        """Convert template to automation creation data."""
        return {
            "organization_id": org_id,
            "name": self.name,
            "description": self.description,
            "trigger_type": self.trigger_type.value,
            "trigger_value": self.trigger_config.get("value", ""),
            "action_type": self.action_type,
            "action_value": self.action_config.get("value", ""),
            "is_active": self.is_active,
            "priority": self.priority,
        }


# Template Library
AUTOMATION_TEMPLATES: List[AutomationTemplate] = [
    AutomationTemplate(
        id="welcome_message",
        name="Welcome Message",
        description="Send a welcome message when a new conversation starts",
        category="greeting",
        trigger_type=TriggerType.NEW_CONVERSATION,
        trigger_config={},
        action_type="auto_reply",
        action_config={
            "value": "Welcome! Thank you for reaching out. We're here to help. What can I assist you with today?"
        },
        priority=10,
    ),
    AutomationTemplate(
        id="business_hours_reply",
        name="Business Hours Auto-Reply",
        description="Send a message outside business hours",
        category="scheduling",
        trigger_type=TriggerType.TIME_BASED,
        trigger_config={
            "hours": [9, 17],  # 9 AM to 5 PM
            "days": [0, 1, 2, 3, 4],  # Mon-Fri
        },
        action_type="auto_reply",
        action_config={
            "value": "Thanks for your message! Our team is currently offline. We'll respond during business hours (9 AM - 5 PM, Mon-Fri)."
        },
        priority=5,
    ),
    AutomationTemplate(
        id="shipping_faq",
        name="Shipping FAQ Auto-Reply",
        description="Answer shipping-related questions automatically",
        category="faq",
        trigger_type=TriggerType.KEYWORD,
        trigger_config={"value": "shipping"},
        action_type="auto_reply",
        action_config={
            "value": "We offer free shipping on orders over $50. Standard delivery takes 3-5 business days. Would you like to know anything else?"
        },
        priority=8,
    ),
    AutomationTemplate(
        id="pricing_faq",
        name="Pricing FAQ Auto-Reply",
        description="Answer pricing-related questions automatically",
        category="faq",
        trigger_type=TriggerType.KEYWORD,
        trigger_config={"value": "price"},
        action_type="auto_reply",
        action_config={
            "value": "Our pricing is competitive and transparent. For detailed pricing information, please visit our website or let me know what product you're interested in!"
        },
        priority=8,
    ),
    AutomationTemplate(
        id="returns_faq",
        name="Returns FAQ Auto-Reply",
        description="Answer return policy questions automatically",
        category="faq",
        trigger_type=TriggerType.KEYWORD,
        trigger_config={"value": "return"},
        action_type="auto_reply",
        action_config={
            "value": "We offer a 30-day return guarantee. Items must be in original condition. Contact our support team to initiate a return."
        },
        priority=8,
    ),
    AutomationTemplate(
        id="lead_qualification",
        name="Lead Qualification Flow",
        description="Qualify leads by asking about their needs",
        category="sales",
        trigger_type=TriggerType.INTENT,
        trigger_config={"intent": "purchase"},
        action_type="auto_reply",
        action_config={
            "value": "Great! I'd love to help. What product or service are you interested in? I can provide recommendations tailored to your needs."
        },
        priority=7,
    ),
    AutomationTemplate(
        id="appointment_booking",
        name="Appointment Booking Prompt",
        description="Prompt customers to book an appointment",
        category="sales",
        trigger_type=TriggerType.KEYWORD,
        trigger_config={"value": "appointment"},
        action_type="auto_reply",
        action_config={
            "value": "I'd be happy to schedule an appointment! Please visit our booking page: [link] or let me know your preferred time."
        },
        priority=7,
    ),
    AutomationTemplate(
        id="order_status",
        name="Order Status Inquiry",
        description="Provide order status information",
        category="support",
        trigger_type=TriggerType.KEYWORD,
        trigger_config={"value": "order status"},
        action_type="auto_reply",
        action_config={
            "value": "I can help you track your order! Please provide your order number and I'll get you the latest status."
        },
        priority=8,
    ),
    AutomationTemplate(
        id="feedback_collection",
        name="Feedback Collection",
        description="Request customer feedback after resolution",
        category="quality",
        trigger_type=TriggerType.MESSAGE_CONTAINS,
        trigger_config={"value": "resolved|solved|fixed|working"},
        action_type="auto_reply",
        action_config={
            "value": "Great! We're glad we could help. Would you mind sharing your feedback? Your input helps us improve."
        },
        priority=6,
    ),
    AutomationTemplate(
        id="escalation_trigger",
        name="Escalation to Human Agent",
        description="Escalate complaint messages to a human agent",
        category="support",
        trigger_type=TriggerType.INTENT,
        trigger_config={"intent": "complaint"},
        action_type="escalate",
        action_config={
            "value": "I'm escalating your case to our support team for immediate assistance. Thank you for your patience."
        },
        priority=9,
    ),
    AutomationTemplate(
        id="language_routing",
        name="Language Detection & Routing",
        description="Detect customer language and route accordingly",
        category="routing",
        trigger_type=TriggerType.MESSAGE_CONTAINS,
        trigger_config={"value": "hola|gracias|por favor"},  # Spanish indicators
        action_type="auto_reply",
        action_config={
            "value": "¡Hola! Parece que prefieres hablar en español. Cambiaré el idioma. ¿Cómo puedo ayudarte?"
        },
        priority=5,
    ),
    AutomationTemplate(
        id="vip_detection",
        name="VIP Customer Detection",
        description="Identify and prioritize VIP customers",
        category="prioritization",
        trigger_type=TriggerType.NEW_CONVERSATION,
        trigger_config={"vip_tags": ["premium", "enterprise"]},
        action_type="notification",
        action_config={
            "value": "VIP customer detected! Please provide priority support."
        },
        priority=10,
    ),
]


def get_template_by_id(template_id: str) -> AutomationTemplate | None:
    """Get a template by ID."""
    for template in AUTOMATION_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_all_templates() -> List[AutomationTemplate]:
    """Get all available templates."""
    return AUTOMATION_TEMPLATES


def get_templates_by_category(category: str) -> List[AutomationTemplate]:
    """Get templates by category."""
    return [t for t in AUTOMATION_TEMPLATES if t.category == category]


def list_categories() -> List[str]:
    """Get list of unique categories."""
    categories = set()
    for template in AUTOMATION_TEMPLATES:
        categories.add(template.category)
    return sorted(list(categories))
