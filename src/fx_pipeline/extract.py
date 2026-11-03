"""Extract step: download exchange rates from the Frankfurter API."""

from __future__ import annotations

from typing import Any

import requests

# ECB reference rates endpoint (Frankfurter v2). A constant, so the address
# is defined in exactly one place.
BASE_URL = "https://api.frankfurter.dev/v2/providers/ecb/rates"


def fetch_rates(
    base: str = "EUR",
    quotes: list[str] | None = None,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    timeout: float = 30.0,
) -> Any:
    """Fetch exchange rates and return the parsed JSON response.

    Use either `date` (one day) or `start_date`/`end_date` (a range).
    With none of them, the API returns the latest available rates.

    Args:
        base: Base currency code, e.g. "EUR".
        quotes: Currency codes to request, e.g. ["USD", "GBP"].
        date: One date as "YYYY-MM-DD".
        start_date: First date of a range, "YYYY-MM-DD".
        end_date: Last date of a range, "YYYY-MM-DD".
        timeout: Seconds to wait before giving up.

    Raises:
        requests.HTTPError: if the API answers with a 4xx/5xx status code.
    """
    params: dict[str, str] = {"base": base}
    if quotes:
        params["quotes"] = ",".join(quotes)  # ["USD", "GBP"] -> "USD,GBP"
    if date:
        params["date"] = date
    if start_date:
        params["from"] = start_date  # our name -> the API's name
    if end_date:
        params["to"] = end_date

    response = requests.get(BASE_URL, params=params, timeout=timeout)
    response.raise_for_status()  # error cards become Python errors
    return response.json()


if __name__ == "__main__":
    import json

    data = fetch_rates(quotes=["USD", "GBP", "CHF", "JPY", "INR"])
    print(json.dumps(data, indent=2))