"""Chatio FastAPI application."""
import logging
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from config import get_settings
from database import init_db
from routers import (
    auth, channels, messages, automations, webhooks, oauth, ai,
    automation_templates, contacts, analytics, team, integrations,
    appointments, translation
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Unified chat dashboard API for LINE, Facebook Messenger, Instagram DM",
    version="0.1.0",
    docs_url="/api/docs" if settings.debug else None,
    openapi_url="/api/openapi.json" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }


# Include routers
app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(messages.router)
app.include_router(automations.router)
app.include_router(webhooks.router)
app.include_router(oauth.router)
app.include_router(ai.router)
app.include_router(automation_templates.router)
app.include_router(contacts.router)
app.include_router(analytics.router)
app.include_router(team.router)
app.include_router(integrations.router)
app.include_router(appointments.router)
app.include_router(translation.router)


# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Welcome to Chatio API",
        "version": "0.1.0",
        "docs": "/api/docs" if settings.debug else None,
    }


# Global exception handler
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    """Handle SQLAlchemy exceptions."""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
