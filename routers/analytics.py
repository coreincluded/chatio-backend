"""Analytics router for retrieving analytics data."""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from database import SessionLocal
from models import User, Organization, Channel, Conversation, Message, Automation, Contact, MessageDirection
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


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


def get_period_days(period: str) -> int:
    """Convert period string to number of days."""
    periods = {"7d": 7, "30d": 30, "90d": 90}
    return periods.get(period, 7)


@router.get("/overview")
async def get_overview(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get analytics overview with key metrics."""
    org = verify_org_access(current_user, org_id, db)

    # Total messages
    total_messages = db.query(func.count(Message.id)).filter(
        Message.conversation_id.in_(
            db.query(Conversation.id).filter(Conversation.organization_id == org_id)
        )
    ).scalar() or 0

    # Total conversations
    total_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.organization_id == org_id
    ).scalar() or 0

    # Active conversations
    active_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.organization_id == org_id,
        Conversation.is_active == True,
    ).scalar() or 0

    # Average response time calculation (in minutes)
    # Get inbound and next outbound message timestamps
    avg_response_time = 0
    inbound_msgs = db.query(Message).join(Conversation).filter(
        Conversation.organization_id == org_id,
        Message.direction == MessageDirection.INBOUND,
    ).all()

    if inbound_msgs:
        response_times = []
        for msg in inbound_msgs:
            next_outbound = db.query(Message).filter(
                Message.conversation_id == msg.conversation_id,
                Message.direction == MessageDirection.OUTBOUND,
                Message.created_at > msg.created_at,
            ).order_by(Message.created_at).first()

            if next_outbound:
                delta = (next_outbound.created_at - msg.created_at).total_seconds() / 60
                response_times.append(delta)

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)

    # Active channels
    active_channels = db.query(func.count(Channel.id)).filter(
        Channel.organization_id == org_id,
        Channel.is_active == True,
    ).scalar() or 0

    return {
        "total_messages": total_messages,
        "total_conversations": total_conversations,
        "active_conversations": active_conversations,
        "avg_response_time": round(avg_response_time, 2),
        "active_channels": active_channels,
    }


@router.get("/messages")
async def get_messages_trend(
    org_id: int,
    period: str = Query("7d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get message volume trend over time grouped by day."""
    org = verify_org_access(current_user, org_id, db)
    days = get_period_days(period)
    start_date = datetime.utcnow() - timedelta(days=days)

    # Group messages by day
    messages = db.query(
        func.date(Message.created_at).label("day"),
        func.count(Message.id).label("count"),
    ).join(Conversation).filter(
        Conversation.organization_id == org_id,
        Message.created_at >= start_date,
    ).group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at)).all()

    return [{"day": str(msg.day), "count": msg.count} for msg in messages]


@router.get("/channels")
async def get_channels_breakdown(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get message and conversation breakdown by channel."""
    org = verify_org_access(current_user, org_id, db)

    channels = db.query(Channel).filter(Channel.organization_id == org_id).all()
    breakdown = []

    for channel in channels:
        msg_count = db.query(func.count(Message.id)).filter(
            Message.channel_id == channel.id
        ).scalar() or 0
        conv_count = db.query(func.count(Conversation.id)).filter(
            Conversation.channel_id == channel.id
        ).scalar() or 0

        breakdown.append({
            "channel_id": channel.id,
            "channel_name": channel.name,
            "channel_type": channel.channel_type.value,
            "message_count": msg_count,
            "conversation_count": conv_count,
        })

    return breakdown


@router.get("/response-times")
async def get_response_times_trend(
    org_id: int,
    period: str = Query("7d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get average response time trend over time grouped by day."""
    org = verify_org_access(current_user, org_id, db)
    days = get_period_days(period)
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get inbound messages in the period
    inbound_msgs = db.query(Message).join(Conversation).filter(
        Conversation.organization_id == org_id,
        Message.direction == MessageDirection.INBOUND,
        Message.created_at >= start_date,
    ).all()

    # Calculate response times grouped by day
    response_by_day = {}
    for msg in inbound_msgs:
        day = msg.created_at.date()
        next_outbound = db.query(Message).filter(
            Message.conversation_id == msg.conversation_id,
            Message.direction == MessageDirection.OUTBOUND,
            Message.created_at > msg.created_at,
        ).order_by(Message.created_at).first()

        if next_outbound:
            delta = (next_outbound.created_at - msg.created_at).total_seconds() / 60
            if day not in response_by_day:
                response_by_day[day] = []
            response_by_day[day].append(delta)

    result = []
    for day in sorted(response_by_day.keys()):
        avg_time = sum(response_by_day[day]) / len(response_by_day[day])
        result.append({"day": str(day), "avg_response_time": round(avg_time, 2)})

    return result


@router.get("/automations")
async def get_automations_stats(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Get automation trigger counts and success rates."""
    org = verify_org_access(current_user, org_id, db)

    automations = db.query(Automation).filter(
        Automation.organization_id == org_id
    ).all()

    stats = []
    for automation in automations:
        # Count triggered messages
        trigger_count = db.query(func.count(Message.id)).filter(
            Message.automation_id == automation.id
        ).scalar() or 0

        stats.append({
            "automation_id": automation.id,
            "automation_name": automation.name,
            "trigger_type": automation.trigger_type.value,
            "is_active": automation.is_active,
            "trigger_count": trigger_count,
        })

    return stats


@router.get("/contacts")
async def get_contacts_stats(
    org_id: int,
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get new contacts over time and lifecycle distribution."""
    org = verify_org_access(current_user, org_id, db)
    days = get_period_days(period)
    start_date = datetime.utcnow() - timedelta(days=days)

    # New contacts over time
    new_contacts = db.query(
        func.date(Contact.created_at).label("day"),
        func.count(Contact.id).label("count"),
    ).filter(
        Contact.organization_id == org_id,
        Contact.created_at >= start_date,
    ).group_by(func.date(Contact.created_at)).order_by(
        func.date(Contact.created_at)
    ).all()

    contacts_trend = [{"day": str(c.day), "count": c.count} for c in new_contacts]

    # Lifecycle distribution
    lifecycle_dist = db.query(
        Contact.lifecycle_stage,
        func.count(Contact.id).label("count"),
    ).filter(
        Contact.organization_id == org_id
    ).group_by(Contact.lifecycle_stage).all()

    lifecycle = [
        {"stage": str(l.lifecycle_stage.value), "count": l.count}
        for l in lifecycle_dist
    ]

    return {
        "new_contacts_trend": contacts_trend,
        "lifecycle_distribution": lifecycle,
    }


@router.get("/export")
async def export_analytics(
    org_id: int,
    format: str = Query("json", regex="^(json|csv)$"),
    period: str = Query("30d", regex="^(7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Export analytics data in JSON or CSV format."""
    org = verify_org_access(current_user, org_id, db)

    # Gather all analytics data
    overview = await get_overview(org_id, current_user, db)
    messages = await get_messages_trend(org_id, period, current_user, db)
    channels = await get_channels_breakdown(org_id, current_user, db)
    response_times = await get_response_times_trend(org_id, period, current_user, db)
    automations = await get_automations_stats(org_id, current_user, db)
    contacts = await get_contacts_stats(org_id, period, current_user, db)

    data = {
        "export_date": datetime.utcnow().isoformat(),
        "organization_id": org_id,
        "period": period,
        "overview": overview,
        "messages_trend": messages,
        "channels_breakdown": channels,
        "response_times_trend": response_times,
        "automations": automations,
        "contacts": contacts,
    }

    if format == "json":
        return data
    elif format == "csv":
        # Convert to CSV format (simplified - returns dict with csv content)
        import csv
        import io

        output = io.StringIO()
        # For simplicity, export overview metrics as CSV
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        for key, value in overview.items():
            writer.writerow([key, value])

        return {
            "format": "csv",
            "content": output.getvalue(),
            "filename": f"analytics_{org_id}_{period}.csv",
        }
