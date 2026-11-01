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
    timeout: float = 10.0,
) -> Any:
    
    params: dict[str, str] = {"base": base}
    if quotes:
        params["quotes"] = ",".join(quotes)  # ["USD", "GBP"] -> "USD,GBP"
    if date:
        params["date"] = date

    response = requests.get(BASE_URL, params=params, timeout=timeout)
    response.raise_for_status()  # error cards become Python errors
    return response.json()


if __name__ == "__main__":
    import json

    data = fetch_rates(quotes=["USD", "GBP", "CHF", "JPY", "INR"])
    print(json.dumps(data, indent=2))