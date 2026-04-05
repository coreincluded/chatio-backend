"""AI-powered services for message suggestions, improvements, and intent detection."""
import logging
import httpx
from typing import List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MessageIntent(str, Enum):
    """Classification of message intent."""
    PURCHASE = "purchase"
    SUPPORT = "support"
    QUESTION = "question"
    COMPLAINT = "complaint"
    GREETING = "greeting"
    OTHER = "other"


class AIProvider(str, Enum):
    """Supported AI providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AIService:
    """Service for AI-powered message features."""

    def __init__(self, api_key: str, provider: str = "openai", model: str = "gpt-3.5-turbo"):
        """
        Initialize AI service.

        Args:
            api_key: API key for the AI provider
            provider: AI provider ("openai" or "anthropic")
            model: Model name to use
        """
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.base_url = self._get_base_url()

    def _get_base_url(self) -> str:
        """Get the base URL for the AI provider."""
        if self.provider == "anthropic":
            return "https://api.anthropic.com/v1"
        else:  # openai
            return "https://api.openai.com/v1"

    async def suggest_reply(
        self,
        conversation_history: List[dict],
        channel_type: str,
        org_settings: Optional[dict] = None,
    ) -> List[str]:
        """
        Generate 3 suggested replies for a conversation.

        Args:
            conversation_history: List of messages with 'role' and 'content'
            channel_type: Type of channel (line_oa, facebook_messenger, etc.)
            org_settings: Organization settings for tone/style preferences

        Returns:
            List of 3 suggested reply messages
        """
        try:
            tone = org_settings.get("tone", "professional") if org_settings else "professional"
            channel = channel_type.replace("_", " ").title()

            if self.provider == "anthropic":
                return await self._suggest_reply_anthropic(conversation_history, channel, tone)
            else:
                return await self._suggest_reply_openai(conversation_history, channel, tone)

        except Exception as e:
            logger.error(f"Error generating reply suggestions: {str(e)}")
            return [
                "Thank you for your message. How can I help?",
                "I appreciate you reaching out. What can I assist with?",
                "Thanks for contacting us. What do you need?",
            ]

    async def _suggest_reply_openai(
        self,
        conversation_history: List[dict],
        channel: str,
        tone: str,
    ) -> List[str]:
        """Generate suggestions using OpenAI API."""
        messages = [
            {
                "role": "system",
                "content": f"""You are a customer service assistant. Generate exactly 3 professional, concise replies to the customer's last message.

Tone: {tone}
Channel: {channel}
Keep replies to 1-2 sentences max. Be helpful and friendly.

Format your response EXACTLY as:
REPLY 1: [first suggestion]
REPLY 2: [second suggestion]
REPLY 3: [third suggestion]""",
            }
        ] + conversation_history

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse suggestions from response
            suggestions = []
            for line in content.split("\n"):
                if line.startswith("REPLY"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        suggestions.append(parts[1].strip())

            return suggestions if len(suggestions) >= 3 else suggestions[:3] if suggestions else []

    async def _suggest_reply_anthropic(
        self,
        conversation_history: List[dict],
        channel: str,
        tone: str,
    ) -> List[str]:
        """Generate suggestions using Anthropic Claude API."""
        messages = [
            {
                "role": "system",
                "content": f"""You are a customer service assistant. Generate exactly 3 professional, concise replies to the customer's last message.

Tone: {tone}
Channel: {channel}
Keep replies to 1-2 sentences max. Be helpful and friendly.

Format your response EXACTLY as:
REPLY 1: [first suggestion]
REPLY 2: [second suggestion]
REPLY 3: [third suggestion]""",
            }
        ] + conversation_history

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 300,
                    "messages": conversation_history,
                    "system": messages[0]["content"],
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["content"][0]["text"]

            # Parse suggestions from response
            suggestions = []
            for line in content.split("\n"):
                if line.startswith("REPLY"):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        suggestions.append(parts[1].strip())

            return suggestions if len(suggestions) >= 3 else suggestions[:3] if suggestions else []

    async def improve_message(self, draft_text: str, tone: str = "professional") -> str:
        """
        Improve a draft message.

        Args:
            draft_text: The message to improve
            tone: Desired tone (professional, casual, friendly)

        Returns:
            Improved version of the message
        """
        try:
            if self.provider == "anthropic":
                return await self._improve_message_anthropic(draft_text, tone)
            else:
                return await self._improve_message_openai(draft_text, tone)

        except Exception as e:
            logger.error(f"Error improving message: {str(e)}")
            return draft_text

    async def _improve_message_openai(self, draft_text: str, tone: str) -> str:
        """Improve message using OpenAI."""
        messages = [
            {
                "role": "system",
                "content": f"""You are a professional copy editor. Improve the following customer service message.

Requirements:
- Tone: {tone}
- Keep it concise (1-3 sentences)
- Maintain the original meaning
- Be helpful and professional
- Only return the improved message, nothing else""",
            },
            {
                "role": "user",
                "content": draft_text,
            },
        ]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 150,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _improve_message_anthropic(self, draft_text: str, tone: str) -> str:
        """Improve message using Anthropic."""
        system_prompt = f"""You are a professional copy editor. Improve the following customer service message.

Requirements:
- Tone: {tone}
- Keep it concise (1-3 sentences)
- Maintain the original meaning
- Be helpful and professional
- Only return the improved message, nothing else"""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 150,
                    "messages": [
                        {
                            "role": "user",
                            "content": draft_text,
                        }
                    ],
                    "system": system_prompt,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()

    async def summarize_conversation(self, messages: List[dict]) -> str:
        """
        Summarize a conversation.

        Args:
            messages: List of messages with 'content' and optionally 'sender'

        Returns:
            Brief summary of the conversation
        """
        try:
            if self.provider == "anthropic":
                return await self._summarize_anthropic(messages)
            else:
                return await self._summarize_openai(messages)

        except Exception as e:
            logger.error(f"Error summarizing conversation: {str(e)}")
            return "Unable to generate summary"

    async def _summarize_openai(self, messages: List[dict]) -> str:
        """Summarize using OpenAI."""
        message_text = "\n".join([f"{m.get('sender', 'Unknown')}: {m['content']}" for m in messages])

        api_messages = [
            {
                "role": "system",
                "content": """Summarize the following customer service conversation in 1-2 sentences.
Focus on the key issue and resolution. Be concise.""",
            },
            {
                "role": "user",
                "content": message_text,
            },
        ]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": api_messages,
                    "temperature": 0.5,
                    "max_tokens": 100,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _summarize_anthropic(self, messages: List[dict]) -> str:
        """Summarize using Anthropic."""
        message_text = "\n".join([f"{m.get('sender', 'Unknown')}: {m['content']}" for m in messages])

        system_prompt = """Summarize the following customer service conversation in 1-2 sentences.
Focus on the key issue and resolution. Be concise."""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 100,
                    "messages": [
                        {
                            "role": "user",
                            "content": message_text,
                        }
                    ],
                    "system": system_prompt,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()

    async def detect_intent(self, message_text: str) -> MessageIntent:
        """
        Detect the intent of a customer message.

        Args:
            message_text: The message to analyze

        Returns:
            MessageIntent classification
        """
        try:
            if self.provider == "anthropic":
                return await self._detect_intent_anthropic(message_text)
            else:
                return await self._detect_intent_openai(message_text)

        except Exception as e:
            logger.error(f"Error detecting intent: {str(e)}")
            return MessageIntent.OTHER

    async def _detect_intent_openai(self, message_text: str) -> MessageIntent:
        """Detect intent using OpenAI."""
        messages = [
            {
                "role": "system",
                "content": f"""Classify the intent of the customer's message into one of these categories:
- {MessageIntent.PURCHASE}: Customer wants to buy/purchase something
- {MessageIntent.SUPPORT}: Customer needs technical support or has an issue
- {MessageIntent.QUESTION}: Customer has a general question
- {MessageIntent.COMPLAINT}: Customer is complaining or expressing dissatisfaction
- {MessageIntent.GREETING}: Customer is greeting or making small talk
- {MessageIntent.OTHER}: Doesn't fit other categories

Respond with ONLY the category name, nothing else.""",
            },
            {
                "role": "user",
                "content": message_text,
            },
        ]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 20,
                },
            )
            response.raise_for_status()
            data = response.json()
            intent_text = data["choices"][0]["message"]["content"].strip().lower()

            # Try to match to enum
            for intent in MessageIntent:
                if intent.value in intent_text:
                    return intent
            return MessageIntent.OTHER

    async def _detect_intent_anthropic(self, message_text: str) -> MessageIntent:
        """Detect intent using Anthropic."""
        system_prompt = f"""Classify the intent of the customer's message into one of these categories:
- {MessageIntent.PURCHASE}: Customer wants to buy/purchase something
- {MessageIntent.SUPPORT}: Customer needs technical support or has an issue
- {MessageIntent.QUESTION}: Customer has a general question
- {MessageIntent.COMPLAINT}: Customer is complaining or expressing dissatisfaction
- {MessageIntent.GREETING}: Customer is greeting or making small talk
- {MessageIntent.OTHER}: Doesn't fit other categories

Respond with ONLY the category name, nothing else."""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 20,
                    "messages": [
                        {
                            "role": "user",
                            "content": message_text,
                        }
                    ],
                    "system": system_prompt,
                },
            )
            response.raise_for_status()
            data = response.json()
            intent_text = data["content"][0]["text"].strip().lower()

            # Try to match to enum
            for intent in MessageIntent:
                if intent.value in intent_text:
                    return intent
            return MessageIntent.OTHER

    async def auto_translate(self, text: str, target_language: str) -> str:
        """
        Translate text to a target language.

        Args:
            text: Text to translate
            target_language: Target language (e.g., "English", "Spanish", "Japanese")

        Returns:
            Translated text
        """
        try:
            if self.provider == "anthropic":
                return await self._auto_translate_anthropic(text, target_language)
            else:
                return await self._auto_translate_openai(text, target_language)

        except Exception as e:
            logger.error(f"Error translating text: {str(e)}")
            return text

    async def _auto_translate_openai(self, text: str, target_language: str) -> str:
        """Translate using OpenAI."""
        messages = [
            {
                "role": "system",
                "content": f"""Translate the following text to {target_language}.
Only return the translated text, nothing else.""",
            },
            {
                "role": "user",
                "content": text,
            },
        ]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _auto_translate_anthropic(self, text: str, target_language: str) -> str:
        """Translate using Anthropic."""
        system_prompt = f"""Translate the following text to {target_language}.
Only return the translated text, nothing else."""

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 500,
                    "messages": [
                        {
                            "role": "user",
                            "content": text,
                        }
                    ],
                    "system": system_prompt,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()


def get_ai_service(api_key: Optional[str], provider: str = "openai", model: str = "gpt-3.5-turbo") -> Optional[AIService]:
    """
    Factory function to create AI service instance.

    Returns None if API key is not configured.
    """
    if not api_key:
        logger.warning("AI API key not configured. AI features will be disabled.")
        return None

    return AIService(api_key=api_key, provider=provider, model=model)
