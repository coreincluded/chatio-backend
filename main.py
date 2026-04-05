"""Chatio FastAPI application."""
import logging
import os
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from config import get_settings
from database import SessionLocal, init_db
from models import User, Organization, Channel, ChannelType, Subscription, SubscriptionTier
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
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_default_channel():
    """Create default admin user, org, and LINE channel from env vars on first run."""
    db = SessionLocal()
    try:
        # Check if any channel exists already
        existing = db.query(Channel).first()
        if existing:
            logger.info("Channels already exist, skipping init")
            return

        line_channel_id = settings.line_channel_id
        line_channel_secret = settings.line_channel_secret
        line_access_token = settings.line_channel_access_token

        if not line_channel_id or not line_access_token:
            logger.info("LINE env vars not set, skipping channel init")
            return

        # Create default admin user if not exists
        admin_user = db.query(User).filter(User.email == "admin@chatio.app").first()
        if not admin_user:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin_user = User(
                email="admin@chatio.app",
                username="admin",
                full_name="Chatio Admin",
                hashed_password=pwd_context.hash(settings.secret_key[:16]),
                is_active=True,
            )
            db.add(admin_user)
            db.flush()
            logger.info(f"Created default admin user (id={admin_user.id})")

        # Create default org if not exists
        org = db.query(Organization).first()
        if not org:
            org = Organization(
                name="Default Organization",
                owner_id=admin_user.id,
            )
            db.add(org)
            db.flush()

            # Create free subscription
            sub = Subscription(
                organization_id=org.id,
                tier=SubscriptionTier.FREE,
                is_active=True,
            )
            db.add(sub)
            db.flush()
            logger.info(f"Created default org (id={org.id})")

        # Create LINE channel
        channel = Channel(
            organization_id=org.id,
            name="\u7d19\u4e0a\u4e16\u754c\u66f8\u574a LINE OA",
            channel_type=ChannelType.LINE_OA,
            external_channel_id=line_channel_id,
            access_token=line_access_token,
            is_active=True,
            extra_data={"channel_secret": line_channel_secret},
        )
        db.add(channel)
        db.commit()
        logger.info(f"Created LINE channel (id={channel.id}) for channel_id={line_channel_id}")

    except Exception as e:
        logger.error(f"Error in init_default_channel: {str(e)}")
        db.rollback()
    finally:
        db.close()


# Initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        init_db()
        logger.info("Database initialized successfully")
        init_default_channel()
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
        "docs": "/api/docs",
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
