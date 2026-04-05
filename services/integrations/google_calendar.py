"""Google Calendar integration connector."""
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .base import BaseIntegration

logger = logging.getLogger(__name__)


class GoogleCalendarIntegration(BaseIntegration):
    """Google Calendar integration for appointment booking."""

    def __init__(self, organization_id: int, config: Dict[str, Any]):
        """Initialize Google Calendar integration."""
        super().__init__(organization_id, "google_calendar", config)
        self.base_url = "https://www.googleapis.com/calendar/v3"

    async def connect(self) -> bool:
        """
        Test connection to Google Calendar API.

        Returns:
            True if OAuth token is valid
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("Google Calendar access token not configured")
                return False

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/calendars/primary",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                logger.info(f"Google Calendar connection successful for org {self.organization_id}")
                return True

        except Exception as e:
            logger.error(f"Google Calendar connection test failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect Google Calendar integration.

        Returns:
            Always True
        """
        self.config.pop("access_token", None)
        self.config.pop("refresh_token", None)
        logger.info(f"Google Calendar integration disconnected for org {self.organization_id}")
        return True

    async def sync(self) -> Dict[str, Any]:
        """
        Sync events from Google Calendar (sample implementation).

        Returns:
            Sync result with stats
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                return {"synced_count": 0, "errors": ["Access token not configured"]}

            synced_count = 0

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/calendars/primary/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "maxResults": 100,
                        "showDeleted": False,
                        "timeMin": datetime.utcnow().isoformat() + "Z",
                    },
                )
                response.raise_for_status()
                data = response.json()
                synced_count = len(data.get("items", []))

            logger.info(f"Google Calendar sync completed: {synced_count} events synced")
            return {"synced_count": synced_count, "errors": []}

        except Exception as e:
            logger.error(f"Error syncing Google Calendar events: {str(e)}")
            return {"synced_count": 0, "errors": [str(e)]}

    async def webhook_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Google Calendar (via Pub/Sub).

        Args:
            payload: Webhook payload

        Returns:
            Response with processing status
        """
        try:
            logger.info(f"Received Google Calendar webhook for org {self.organization_id}")
            return {
                "success": True,
                "organization_id": self.organization_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error handling Google Calendar webhook: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        attendee_email: Optional[str] = None,
        timezone: str = "UTC",
    ) -> Optional[str]:
        """
        Create an event in Google Calendar.

        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description
            attendee_email: Attendee email to send invite
            timezone: Timezone for the event

        Returns:
            Event ID if successful
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("Google Calendar access token not configured")
                return None

            event = {
                "summary": title,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": timezone,
                },
            }

            if description:
                event["description"] = description

            if attendee_email:
                event["attendees"] = [{"email": attendee_email}]

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.base_url}/calendars/primary/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=event,
                )
                response.raise_for_status()
                data = response.json()
                event_id = data.get("id")
                logger.info(f"Event created in Google Calendar: {event_id}")
                return event_id

        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {str(e)}")
            return None

    async def get_available_slots(
        self,
        date: str,  # YYYY-MM-DD
        duration_minutes: int = 30,
        timezone: str = "UTC",
    ) -> List[Dict[str, str]]:
        """
        Get available time slots for a given date.

        Args:
            date: Date in YYYY-MM-DD format
            duration_minutes: Duration of each slot
            timezone: Timezone for the date

        Returns:
            List of available slots with start and end times
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("Google Calendar access token not configured")
                return []

            # Get events for the date
            start_time = datetime.fromisoformat(f"{date}T00:00:00")
            end_time = start_time + timedelta(days=1)

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/calendars/primary/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "timeMin": start_time.isoformat() + "Z",
                        "timeMax": end_time.isoformat() + "Z",
                        "maxResults": 100,
                    },
                )
                response.raise_for_status()
                data = response.json()
                events = data.get("items", [])

            # Calculate available slots (simple implementation: 9am-5pm)
            slots = []
            current = start_time.replace(hour=9, minute=0, second=0)
            end = start_time.replace(hour=17, minute=0, second=0)

            while current + timedelta(minutes=duration_minutes) <= end:
                slot_end = current + timedelta(minutes=duration_minutes)

                # Check if slot conflicts with existing events
                is_available = True
                for event in events:
                    event_start = datetime.fromisoformat(
                        event.get("start", {}).get("dateTime", "").replace("Z", "+00:00")
                    )
                    event_end = datetime.fromisoformat(
                        event.get("end", {}).get("dateTime", "").replace("Z", "+00:00")
                    )
                    if not (slot_end <= event_start or current >= event_end):
                        is_available = False
                        break

                if is_available:
                    slots.append({
                        "start": current.isoformat(),
                        "end": slot_end.isoformat(),
                    })

                current += timedelta(minutes=duration_minutes)

            logger.info(f"Found {len(slots)} available slots for {date}")
            return slots

        except Exception as e:
            logger.error(f"Error getting available slots: {str(e)}")
            return []

    def _get_access_token(self) -> Optional[str]:
        """Get access token from config."""
        return self.config.get("access_token")
