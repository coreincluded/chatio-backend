"""OAuth router for channel connections."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import urlencode
import httpx
import secrets

from database import SessionLocal
from models import User, Organization, Channel, ChannelType
from routers.auth import get_current_user
from config import get_settings

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])
settings = get_settings()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============ LINE OA ============
@router.get("/line/authorize")
async def line_authorize(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Get LINE OAuth authorization URL."""
    # Check if LINE credentials are configured
    if not settings.line_channel_id or not settings.line_channel_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LINE OAuth is not configured. Please set LINE_CHANNEL_ID and LINE_CHANNEL_SECRET in environment variables.",
        )

    state = f"{current_user.id}:{org_id}:{secrets.token_urlsafe(16)}"
    params = {
        "response_type": "code",
        "client_id": settings.line_channel_id,
        "redirect_uri": f"{settings.app_url}/api/v1/oauth/line/callback",
        "state": state,
        "scope": "profile openid",
        "bot_prompt": "aggressive",
    }
    auth_url = f"https://access.line.me/oauth2/v2.1/authorize?{urlencode(params)}"
    return {"authorize_url": auth_url, "state": state}

@router.get("/line/callback")
async def line_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle LINE OAuth callback."""
    try:
        parts = state.split(":")
        user_id = int(parts[0])
        org_id = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.app_url}/api/v1/oauth/line/callback",
                "client_id": settings.line_channel_id,
                "client_secret": settings.line_channel_secret,
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange LINE authorization code")

    token_data = token_response.json()
    access_token = token_data.get("access_token", "")

    # Get LINE bot info
    async with httpx.AsyncClient() as client:
        bot_response = await client.get(
            "https://api.line.me/v2/bot/info",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    bot_info = bot_response.json() if bot_response.status_code == 200 else {}
    bot_name = bot_info.get("displayName", "LINE Official Account")
    bot_id = bot_info.get("userId", settings.line_channel_id)

    # Check if channel already exists
    existing = db.query(Channel).filter(
        Channel.organization_id == org_id,
        Channel.external_channel_id == bot_id,
    ).first()

    if existing:
        # Update existing channel
        existing.access_token = access_token
        existing.is_active = True
        existing.name = bot_name
        db.commit()
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=line&status=updated")

    # Create new channel
    channel = Channel(
        organization_id=org_id,
        name=bot_name,
        channel_type=ChannelType.LINE_OA,
        external_channel_id=bot_id,
        access_token=access_token,
    )
    db.add(channel)
    db.commit()

    return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=line&status=success")

# ============ FACEBOOK (Messenger + Instagram) ============
@router.get("/facebook/authorize")
async def facebook_authorize(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Get Facebook OAuth authorization URL (covers Messenger + Instagram)."""
    # Check if Facebook credentials are configured
    if not settings.facebook_app_id or not settings.facebook_app_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook OAuth is not configured. Please set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in environment variables.",
        )

    state = f"{current_user.id}:{org_id}:{secrets.token_urlsafe(16)}"
    params = {
        "client_id": settings.facebook_app_id,
        "redirect_uri": f"{settings.app_url}/api/v1/oauth/facebook/callback",
        "state": state,
        "scope": "pages_messaging,pages_show_list,pages_manage_metadata,instagram_basic,instagram_manage_messages",
        "response_type": "code",
    }
    auth_url = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"
    return {"authorize_url": auth_url, "state": state}

@router.get("/facebook/callback")
async def facebook_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Facebook OAuth callback — creates Messenger and/or Instagram channels."""
    try:
        parts = state.split(":")
        user_id = int(parts[0])
        org_id = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for user access token
    async with httpx.AsyncClient() as client:
        token_response = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": settings.facebook_app_id,
                "client_secret": settings.facebook_app_secret,
                "redirect_uri": f"{settings.app_url}/api/v1/oauth/facebook/callback",
                "code": code,
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Facebook authorization code")

    user_token = token_response.json().get("access_token", "")

    # Get user's pages (for Messenger)
    async with httpx.AsyncClient() as client:
        pages_response = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": user_token},
        )

    channels_created = []

    if pages_response.status_code == 200:
        pages = pages_response.json().get("data", [])
        for page in pages:
            page_id = page["id"]
            page_name = page["name"]
            page_token = page["access_token"]

            # Create/update Messenger channel
            existing = db.query(Channel).filter(
                Channel.organization_id == org_id,
                Channel.external_channel_id == page_id,
                Channel.channel_type == ChannelType.FACEBOOK_MESSENGER,
            ).first()

            if existing:
                existing.access_token = page_token
                existing.is_active = True
                existing.name = f"{page_name} (Messenger)"
            else:
                channel = Channel(
                    organization_id=org_id,
                    name=f"{page_name} (Messenger)",
                    channel_type=ChannelType.FACEBOOK_MESSENGER,
                    external_channel_id=page_id,
                    access_token=page_token,
                )
                db.add(channel)
            channels_created.append("messenger")

            # Check for Instagram Business Account linked to this page
            async with httpx.AsyncClient() as client:
                ig_response = await client.get(
                    f"https://graph.facebook.com/v19.0/{page_id}",
                    params={
                        "fields": "instagram_business_account",
                        "access_token": page_token,
                    },
                )

            if ig_response.status_code == 200:
                ig_data = ig_response.json().get("instagram_business_account")
                if ig_data:
                    ig_id = ig_data["id"]

                    existing_ig = db.query(Channel).filter(
                        Channel.organization_id == org_id,
                        Channel.external_channel_id == ig_id,
                        Channel.channel_type == ChannelType.INSTAGRAM_DM,
                    ).first()

                    if existing_ig:
                        existing_ig.access_token = page_token
                        existing_ig.is_active = True
                    else:
                        ig_channel = Channel(
                            organization_id=org_id,
                            name=f"{page_name} (Instagram)",
                            channel_type=ChannelType.INSTAGRAM_DM,
                            external_channel_id=ig_id,
                            access_token=page_token,
                        )
                        db.add(ig_channel)
                    channels_created.append("instagram")

    db.commit()
    connected = ",".join(channels_created) or "none"
    return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected={connected}&status=success")


# ============ TWITTER/X ============
@router.get("/twitter/authorize")
async def twitter_authorize(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Get Twitter/X OAuth authorization URL."""
    # Check if Twitter credentials are configured
    if not settings.twitter_client_id or not settings.twitter_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Twitter/X OAuth is not configured. Please set TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET in environment variables.",
        )

    state = f"{current_user.id}:{org_id}:{secrets.token_urlsafe(16)}"
    params = {
        "response_type": "code",
        "client_id": settings.twitter_client_id,
        "redirect_uri": f"{settings.app_url}/api/v1/oauth/twitter/callback",
        "state": state,
        "scope": "tweet.read tweet.write users.read follows.read follows.write offline.access",
        "code_challenge": secrets.token_urlsafe(32),
        "code_challenge_method": "S256",
    }
    auth_url = f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"
    return {"authorize_url": auth_url, "state": state}

@router.get("/twitter/callback")
async def twitter_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Twitter/X OAuth callback."""
    try:
        parts = state.split(":")
        user_id = int(parts[0])
        org_id = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.app_url}/api/v1/oauth/twitter/callback",
                "client_id": settings.twitter_client_id,
                "client_secret": settings.twitter_client_secret,
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange Twitter authorization code")

    token_data = token_response.json()
    access_token = token_data.get("access_token", "")

    # Get Twitter user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    user_info = user_response.json() if user_response.status_code == 200 else {}
    user_data = user_info.get("data", {})
    twitter_id = user_data.get("id", settings.twitter_client_id)
    twitter_name = user_data.get("name", "Twitter Account")

    # Check if channel already exists
    existing = db.query(Channel).filter(
        Channel.organization_id == org_id,
        Channel.external_channel_id == twitter_id,
    ).first()

    if existing:
        existing.access_token = access_token
        existing.is_active = True
        existing.name = twitter_name
        db.commit()
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=twitter&status=updated")

    # Create new channel
    channel = Channel(
        organization_id=org_id,
        name=twitter_name,
        channel_type=ChannelType.TWITTER_X,
        external_channel_id=twitter_id,
        access_token=access_token,
    )
    db.add(channel)
    db.commit()

    return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=twitter&status=success")

# ============ LINKEDIN ============
@router.get("/linkedin/authorize")
async def linkedin_authorize(
    org_id: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Get LinkedIn OAuth authorization URL."""
    # Check if LinkedIn credentials are configured
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LinkedIn OAuth is not configured. Please set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in environment variables.",
        )

    state = f"{current_user.id}:{org_id}:{secrets.token_urlsafe(16)}"
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": f"{settings.app_url}/api/v1/oauth/linkedin/callback",
        "state": state,
        "scope": "w_member_social r_basicprofile",
    }
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"
    return {"authorize_url": auth_url, "state": state}

@router.get("/linkedin/callback")
async def linkedin_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle LinkedIn OAuth callback."""
    try:
        parts = state.split(":")
        user_id = int(parts[0])
        org_id = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{settings.app_url}/api/v1/oauth/linkedin/callback",
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange LinkedIn authorization code")

    token_data = token_response.json()
    access_token = token_data.get("access_token", "")

    # Get LinkedIn user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.linkedin.com/v2/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    user_info = user_response.json() if user_response.status_code == 200 else {}
    linkedin_id = user_info.get("id", settings.linkedin_client_id)
    linkedin_name = f"{user_info.get('localizedFirstName', 'LinkedIn')} {user_info.get('localizedLastName', 'User')}"

    # Check if channel already exists
    existing = db.query(Channel).filter(
        Channel.organization_id == org_id,
        Channel.external_channel_id == linkedin_id,
    ).first()

    if existing:
        existing.access_token = access_token
        existing.is_active = True
        existing.name = linkedin_name
        db.commit()
        return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=linkedin&status=updated")

    # Create new channel
    channel = Channel(
        organization_id=org_id,
        name=linkedin_name,
        channel_type=ChannelType.LINKEDIN,
        external_channel_id=linkedin_id,
        access_token=access_token,
    )
    db.add(channel)
    db.commit()

    return RedirectResponse(url=f"{settings.frontend_url}/dashboard/channels?connected=linkedin&status=success")

# ============ Connection status ============
@router.get("/status")
async def oauth_status(
    current_user: User = Depends(get_current_user),
):
    """Return which OAuth providers are configured."""
    return {
        "line": {
            "configured": bool(settings.line_channel_id and settings.line_channel_secret),
            "name": "LINE Official Account",
        },
        "facebook": {
            "configured": bool(settings.facebook_app_id and settings.facebook_app_secret),
            "name": "Facebook (Messenger + Instagram)",
        },
        "twitter": {
            "configured": bool(settings.twitter_client_id and settings.twitter_client_secret),
            "name": "Twitter/X",
        },
        "linkedin": {
            "configured": bool(settings.linkedin_client_id and settings.linkedin_client_secret),
            "name": "LinkedIn",
        },
    }
