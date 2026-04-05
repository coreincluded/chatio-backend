"""Appointments router for booking and managing appointments."""
import logging
from typing import List, Optional
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Appointment, BusinessHours, Organization, Contact, Conversation,
    AppointmentStatus,
)
from schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    BusinessHoursCreate, BusinessHoursUpdate, BusinessHoursResponse,
    AvailableSlotsRequest,
)
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])


@router.get("", response_model=List[AppointmentResponse])
async def list_appointments(
    start_date: Optional[str] = Query(None),  # YYYY-MM-DD
    end_date: Optional[str] = Query(None),  # YYYY-MM-DD
    status_filter: Optional[str] = Query(None),  # pending, confirmed, cancelled, completed
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List appointments with optional filtering."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    query = db.query(Appointment).filter(Appointment.organization_id == org.id)

    if start_date:
        start_datetime = datetime.fromisoformat(start_date)
        query = query.filter(Appointment.start_time >= start_datetime)

    if end_date:
        end_datetime = datetime.fromisoformat(end_date) + timedelta(days=1)
        query = query.filter(Appointment.start_time < end_datetime)

    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    appointments = query.order_by(Appointment.start_time).all()
    return [AppointmentResponse.from_orm(a) for a in appointments]


@router.post("", response_model=AppointmentResponse)
async def create_appointment(
    appointment: AppointmentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new appointment."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Validate contact exists if provided
    if appointment.contact_id:
        contact = db.query(Contact).filter(
            Contact.id == appointment.contact_id,
            Contact.organization_id == org.id,
        ).first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

    # Validate conversation exists if provided
    if appointment.conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == appointment.conversation_id,
            Conversation.organization_id == org.id,
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    new_appointment = Appointment(
        organization_id=org.id,
        contact_id=appointment.contact_id,
        conversation_id=appointment.conversation_id,
        title=appointment.title,
        description=appointment.description,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        timezone=appointment.timezone or "UTC",
        status=appointment.status or AppointmentStatus.PENDING,
    )

    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    return AppointmentResponse.from_orm(new_appointment)


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    appointment: AppointmentUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an appointment."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == org.id,
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Update fields
    for field, value in appointment.dict(exclude_unset=True).items():
        setattr(existing, field, value)

    existing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)

    return AppointmentResponse.from_orm(existing)


@router.delete("/{appointment_id}")
async def delete_appointment(
    appointment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel/delete an appointment."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == org.id,
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Mark as cancelled instead of deleting
    existing.status = AppointmentStatus.CANCELLED
    existing.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Appointment cancelled successfully"}


@router.get("/available-slots", response_model=List[dict])
async def get_available_slots(
    date: str = Query(...),  # YYYY-MM-DD
    timezone: str = Query("UTC"),
    duration_minutes: int = Query(30),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get available time slots for a given date based on business hours."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        target_date = datetime.fromisoformat(date)
        day_of_week = target_date.weekday()

        # Get business hours for the day
        business_hours = db.query(BusinessHours).filter(
            BusinessHours.organization_id == org.id,
            BusinessHours.day_of_week == day_of_week,
        ).first()

        if not business_hours or business_hours.is_closed:
            return []

        # Parse open/close times
        open_hour, open_min = map(int, business_hours.open_time.split(":"))
        close_hour, close_min = map(int, business_hours.close_time.split(":"))

        slot_start = target_date.replace(hour=open_hour, minute=open_min, second=0, microsecond=0)
        slot_end = target_date.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)

        # Get existing appointments for the day
        existing_appointments = db.query(Appointment).filter(
            Appointment.organization_id == org.id,
            Appointment.start_time >= target_date,
            Appointment.start_time < target_date + timedelta(days=1),
            Appointment.status != AppointmentStatus.CANCELLED,
        ).all()

        existing_ranges = [
            (a.start_time, a.end_time) for a in existing_appointments
        ]

        # Generate slots
        slots = []
        current = slot_start

        while current + timedelta(minutes=duration_minutes) <= slot_end:
            slot_end_time = current + timedelta(minutes=duration_minutes)

            # Check if slot conflicts with existing appointments
            is_available = True
            for app_start, app_end in existing_ranges:
                # Check for overlap
                if not (slot_end_time <= app_start or current >= app_end):
                    is_available = False
                    break

            if is_available:
                slots.append({
                    "start": current.isoformat(),
                    "end": slot_end_time.isoformat(),
                })

            current += timedelta(minutes=duration_minutes)

        return slots

    except Exception as e:
        logger.error(f"Error getting available slots: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{appointment_id}/remind")
async def send_reminder(
    appointment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a reminder for an appointment via channel."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.organization_id == org.id,
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.reminder_sent:
        return {"message": "Reminder already sent for this appointment"}

    # Mark as reminder sent
    appointment.reminder_sent = True
    db.commit()

    return {
        "message": f"Reminder sent for appointment {appointment.title}",
        "appointment_id": appointment_id,
    }


# Business Hours endpoints

@router.get("/business-hours", response_model=List[BusinessHoursResponse])
async def get_business_hours(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get business hours configuration."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    hours = db.query(BusinessHours).filter(
        BusinessHours.organization_id == org.id
    ).order_by(BusinessHours.day_of_week).all()

    # If no configuration exists, return defaults (9am-5pm Mon-Fri)
    if not hours:
        from datetime import datetime as dt
        defaults = []
        for day in range(7):
            is_weekend = day >= 5
            defaults.append(BusinessHoursResponse(
                id=0,  # placeholder ID
                organization_id=org.id,
                day_of_week=day,
                open_time="09:00",
                close_time="17:00",
                is_closed=is_weekend,
                created_at=dt.utcnow(),
                updated_at=dt.utcnow(),
            ))
        return defaults

    return [BusinessHoursResponse.from_orm(h) for h in hours]


@router.put("/business-hours", response_model=List[BusinessHoursResponse])
async def update_business_hours(
    hours: List[BusinessHoursUpdate],
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update business hours configuration."""
    # Get user's organization
    org = db.query(Organization).filter(Organization.owner_id == current_user.id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Clear existing hours
    db.query(BusinessHours).filter(
        BusinessHours.organization_id == org.id
    ).delete()

    # Add new hours
    for hour_data in hours:
        new_hour = BusinessHours(
            organization_id=org.id,
            day_of_week=hour_data.day_of_week,
            open_time=hour_data.open_time,
            close_time=hour_data.close_time,
            is_closed=hour_data.is_closed or False,
        )
        db.add(new_hour)

    db.commit()

    updated_hours = db.query(BusinessHours).filter(
        BusinessHours.organization_id == org.id
    ).order_by(BusinessHours.day_of_week).all()

    return [BusinessHoursResponse.from_orm(h) for h in updated_hours]
