"""Authentication router with JWT."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import EmailStr

from database import SessionLocal
from models import User
from schemas import UserCreate, LoginRequest, UserResponse, Token, TokenData
from config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Auto-create default organization and subscription for new user
    from models import Organization, Subscription, SubscriptionTier
    default_org = Organization(
        owner_id=new_user.id,
        name=f"{new_user.username}'s Organization",
        description="Default organization",
    )
    db.add(default_org)
    db.commit()
    db.refresh(default_org)

    # Create free subscription
    subscription = Subscription(
        organization_id=default_org.id,
        tier=SubscriptionTier.FREE,
    )
    db.add(subscription)
    db.commit()

    return new_user


@router.post("/login", response_model=Token)
async def login(user_data: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    from models import Organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat(),
        "organization_id": org.id if org else None,
        "organization_name": org.name if org else None,
    }


@router.post("/logout")
async def logout():
    """Logout endpoint. Token invalidation handled client-side."""
    return {"message": "Successfully logged out"}



# --- Password Reset ---


def create_reset_token(user_id: int) -> str:
    """Create a short-lived reset token (15 min)."""
    return create_access_token(
        data={"sub": str(user_id), "type": "reset"},
        expires_delta=timedelta(minutes=15),
    )


@router.post("/forgot-password")
async def forgot_password(
    request_data: dict,
    db: Session = Depends(get_db),
) -> dict:
    email = request_data.get("email", "")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"message": "If that email is registered, a reset link has been sent.", "reset_token": None}
    token = create_reset_token(user.id)
    # Send reset email
    try:
        from email_service import send_reset_email
        from config import get_settings as _gs
        send_reset_email(email, token, base_url=_gs().frontend_url)
    except Exception as e:
        print(f"[auth] email send failed: {e}")
    return {"message": "Reset token generated.", "reset_token": token}


@router.post("/reset-password")
async def reset_password(
    request_data: dict,
    db: Session = Depends(get_db),
) -> dict:
    token = request_data.get("token", "")
    new_password = request_data.get("new_password", "")
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new_password required")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(new_password)
    db.commit()
    return {"message": "Password reset successful. You can now log in."}
