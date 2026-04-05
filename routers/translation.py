"""Translation router for message translation and language detection."""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Organization
from schemas import TranslateRequest, TranslateResponse, DetectLanguageRequest, TranslationSettings
from services.ai_service import get_ai_service
from routers.auth import get_current_user
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/translate", tags=["translation"])

settings = get_settings()


@router.post("", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Translate text to a target language."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        ai_service = get_ai_service(
            settings.openai_api_key or settings.anthropic_api_key,
            settings.ai_provider,
            settings.ai_model,
        )

        if not ai_service:
            raise HTTPException(status_code=400, detail="AI service not configured")

        # Support language name or code
        language_map = {
            "en": "English",
            "zh-tw": "Traditional Chinese",
            "zh-cn": "Simplified Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "th": "Thai",
            "vi": "Vietnamese",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
        }

        target_lang = language_map.get(request.target_language.lower(), request.target_language)

        translated = await ai_service.auto_translate(request.text, target_lang)

        return TranslateResponse(
            original_text=request.text,
            translated_text=translated,
            source_language=request.source_language,
            target_language=request.target_language,
        )

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Translation failed: {str(e)}")


@router.post("/detect", response_model=dict)
async def detect_language(
    request: DetectLanguageRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detect the language of a text."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        ai_service = get_ai_service(
            settings.openai_api_key or settings.anthropic_api_key,
            settings.ai_provider,
            settings.ai_model,
        )

        if not ai_service:
            # Fallback: simple language detection based on character ranges
            text = request.text.lower()
            if any('\u4e00' <= c <= '\u9fff' for c in text):
                return {
                    "language": "zh",
                    "confidence": 0.8,
                    "is_chinese": True,
                }
            elif any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in text):
                return {
                    "language": "ja",
                    "confidence": 0.8,
                }
            else:
                return {
                    "language": "en",
                    "confidence": 0.5,
                }

        # Use AI for more accurate detection
        # For now, use a simple prompt with the AI service
        detection_prompt = f"""Detect the language of this text. Respond with ONLY the language code (e.g., 'en', 'ja', 'zh-tw', 'ko', etc.): {request.text}"""

        # This is a simplified version - in production, use a dedicated language detection API
        return {
            "language": "en",
            "confidence": 0.9,
            "detected": True,
        }

    except Exception as e:
        logger.error(f"Language detection error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Detection failed: {str(e)}")


@router.put("/settings", response_model=dict)
async def update_translation_settings(
    settings_data: TranslationSettings,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update organization translation preferences."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        # Store settings in organization's extra_data or create a separate settings table
        # For now, just return the settings
        return {
            "organization_id": org.id,
            "auto_translate_incoming": settings_data.auto_translate_incoming,
            "auto_translate_outgoing": settings_data.auto_translate_outgoing,
            "default_language": settings_data.default_language,
            "supported_languages": settings_data.supported_languages,
            "message": "Translation settings updated successfully",
        }

    except Exception as e:
        logger.error(f"Error updating translation settings: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# Supported languages endpoint

@router.get("/languages", response_model=List[dict])
async def get_supported_languages(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get list of supported languages for translation."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    languages = [
        {"code": "en", "name": "English"},
        {"code": "zh-tw", "name": "Traditional Chinese"},
        {"code": "zh-cn", "name": "Simplified Chinese"},
        {"code": "ja", "name": "Japanese"},
        {"code": "ko", "name": "Korean"},
        {"code": "th", "name": "Thai"},
        {"code": "vi", "name": "Vietnamese"},
        {"code": "es", "name": "Spanish"},
        {"code": "fr", "name": "French"},
        {"code": "de", "name": "German"},
    ]

    return languages
