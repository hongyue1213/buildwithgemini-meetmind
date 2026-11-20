"""Calendar and holiday tools for MeetMind meeting scheduling and deadline planning."""
import os
from typing import Any, Dict, List
import httpx


def get_public_holidays(country_code: str = "US", year: int = 0) -> List[Dict[str, Any]]:
    """Fetches public holidays for a country to assist with meeting scheduling and deadline planning.

    Args:
        country_code: Two-letter ISO country code (e.g., 'US', 'GB', 'TW', 'JP'). Default is 'US'.
        year: Specific calendar year (e.g., 2026). If 0 or omitted, returns upcoming holidays.

    Returns:
        A list of public holidays containing date, English name, local name, and country code.
    """
    base_url = os.getenv("HOLIDAY_API_BASE_URL", "https://date.nager.at/api/v3").rstrip("/")
    api_key = os.getenv("HOLIDAY_API_KEY", "")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    country = country_code.strip().upper() or "US"
    if year and year > 1900:
        url = f"{base_url}/PublicHolidays/{year}/{country}"
    else:
        url = f"{base_url}/NextPublicHolidays/{country}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return [{"error": f"Failed to fetch holidays: HTTP {resp.status_code}"}]
            data = resp.json()
            holidays = []
            for item in data:
                holidays.append({
                    "date": item.get("date"),
                    "name": item.get("name"),
                    "local_name": item.get("localName"),
                    "country_code": item.get("countryCode"),
                })
            return holidays
    except Exception as e:
        return [{"error": f"Error querying public holiday API: {str(e)}"}]
