"""CSV export utility for analytics."""

import csv
import io

from app.schemas.analytics import GuestLeadResponse


def generate_guest_leads_csv(guests: list[GuestLeadResponse]) -> str:
    """Generate a CSV string from a list of guest leads."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Phone", "First Visited", "Photos Matched", "Photos Downloaded"])
    for guest in guests:
        writer.writerow(
            [
                guest.guest_name,
                guest.guest_phone,
                guest.first_visit.isoformat() if guest.first_visit else "",
                guest.photos_matched_count,
                guest.download_count,
            ]
        )
    return output.getvalue()
