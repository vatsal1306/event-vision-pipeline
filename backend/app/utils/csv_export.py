"""CSV export utility for analytics."""

import csv
import io

from app.schemas.analytics import GuestLeadResponse


def generate_guest_leads_csv(guests: list[GuestLeadResponse]) -> str:
    """Generate a CSV string from a list of guest leads."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Name", "Phone", "First Visited", "Photos Matched", "Photos Downloaded"]
    )
    for guest in guests:
        writer.writerow(
            [
                guest.name,
                guest.phone,
                guest.first_visited.isoformat() if guest.first_visited else "",
                guest.photos_matched,
                guest.photos_downloaded,
            ]
        )
    return output.getvalue()
