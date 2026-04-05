"""Team management router for RBAC and team collaboration."""
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import SessionLocal
from models import User, Organization, TeamMember, TeamMemberRole, Conversation, ConversationAssignment
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/team", tags=["team"])


# Pydantic schemas
class TeamMemberResponse(BaseModel):
    id: int
    user_id: int
    organization_id: int
    role: str
    invited_at: datetime
    accepted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamMemberInvite(BaseModel):
    email: EmailStr
    role: str = "agent"  # admin, agent, viewer


class TeamMemberRoleUpdate(BaseModel):
    role: str  # admin, agent, viewer


class ConversationAssignRequest(BaseModel):
    team_member_id: int


class AssignedConversationResponse(BaseModel):
    id: int
    external_conversation_id: str
    customer_name: Optional[str]
    assigned_to: int
    assigned_at: datetime

    class Config:
        from_attributes = True


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


def get_user_role(user: User, org_id: int, db: Session) -> Optional[str]:
    """Get the role of a user in an organization."""
    if user.organizations and any(org.id == org_id for org in user.organizations):
        return "admin"  # Owner is admin

    team_member = db.query(TeamMember).filter(
        TeamMember.user_id == user.id,
        TeamMember.organization_id == org_id,
    ).first()

    return team_member.role.value if team_member else None


def require_admin(user: User, org_id: int, db: Session) -> TeamMemberRole:
    """Verify user is admin in organization."""
    # Check if owner
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and org.owner_id == user.id:
        return TeamMemberRole.ADMIN

    # Check team member role
    team_member = db.query(TeamMember).filter(
        TeamMember.user_id == user.id,
        TeamMember.organization_id == org_id,
    ).first()

    if not team_member or team_member.role != TeamMemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return team_member.role


# ============ Team Member endpoints ============


@router.get("/members", response_model=List[TeamMemberResponse])
async def list_team_members(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TeamMember]:
    """List all team members in an organization."""
    org = verify_org_access(current_user, org_id, db)

    team_members = db.query(TeamMember).filter(
        TeamMember.organization_id == org_id
    ).all()

    return team_members


@router.post("/invite", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    org_id: int,
    invite_data: TeamMemberInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamMember:
    """Invite a new team member (admin only)."""
    org = verify_org_access(current_user, org_id, db)
    require_admin(current_user, org_id, db)

    # Validate role
    try:
        role = TeamMemberRole[invite_data.role.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: admin, agent, or viewer",
        )

    # Find or create user
    user = db.query(User).filter(User.email == invite_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found. User must register first.",
        )

    # Check if already a team member
    existing = db.query(TeamMember).filter(
        TeamMember.user_id == user.id,
        TeamMember.organization_id == org_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a team member",
        )

    # Create team member
    team_member = TeamMember(
        user_id=user.id,
        organization_id=org_id,
        role=role,
    )

    db.add(team_member)
    db.commit()
    db.refresh(team_member)
    return team_member


@router.put("/members/{member_id}/role", response_model=TeamMemberResponse)
async def update_team_member_role(
    org_id: int,
    member_id: int,
    role_data: TeamMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeamMember:
    """Update a team member's role (admin only)."""
    org = verify_org_access(current_user, org_id, db)
    require_admin(current_user, org_id, db)

    # Validate role
    try:
        new_role = TeamMemberRole[role_data.role.upper()]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: admin, agent, or viewer",
        )

    # Get team member
    team_member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.organization_id == org_id,
    ).first()

    if not team_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    team_member.role = new_role
    db.commit()
    db.refresh(team_member)
    return team_member


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    org_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove a team member (admin only)."""
    org = verify_org_access(current_user, org_id, db)
    require_admin(current_user, org_id, db)

    team_member = db.query(TeamMember).filter(
        TeamMember.id == member_id,
        TeamMember.organization_id == org_id,
    ).first()

    if not team_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Remove assignments for this team member
    db.query(ConversationAssignment).filter(
        ConversationAssignment.assigned_to == member_id
    ).delete()

    db.delete(team_member)
    db.commit()


# ============ Conversation Assignment endpoints ============


@router.post("/conversations/{conversation_id}/assign", status_code=status.HTTP_200_OK)
async def assign_conversation(
    org_id: int,
    conversation_id: int,
    assign_data: ConversationAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Assign a conversation to a team member (admin/agent)."""
    org = verify_org_access(current_user, org_id, db)

    # Check permission (admin or agent can assign)
    user_role = get_user_role(current_user, org_id, db)
    if user_role not in ["admin", "agent"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and agents can assign conversations",
        )

    # Get conversation
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.organization_id == org_id,
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Get target team member
    target_member = db.query(TeamMember).filter(
        TeamMember.id == assign_data.team_member_id,
        TeamMember.organization_id == org_id,
    ).first()

    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    # Get current user as team member
    current_member = db.query(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.organization_id == org_id,
    ).first()

    # Remove existing assignment if any
    db.query(ConversationAssignment).filter(
        ConversationAssignment.conversation_id == conversation_id
    ).delete()

    # Create new assignment
    assignment = ConversationAssignment(
        conversation_id=conversation_id,
        assigned_to=target_member.id,
        assigned_by=current_member.id if current_member else None,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "success": True,
        "message": f"Conversation assigned to {target_member.user.full_name or target_member.user.username}",
        "assignment_id": assignment.id,
    }


@router.get("/conversations/assigned", response_model=List[AssignedConversationResponse])
async def get_assigned_conversations(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Conversation]:
    """Get conversations assigned to the current user."""
    org = verify_org_access(current_user, org_id, db)

    # Get current user as team member
    team_member = db.query(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.organization_id == org_id,
    ).first()

    if not team_member:
        return []

    # Get assigned conversations
    assigned = db.query(Conversation).join(ConversationAssignment).filter(
        ConversationAssignment.assigned_to == team_member.id
    ).all()

    return assigned
