"""Extract step: download exchange rates from the Frankfurter API."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("fx_pipeline.extract")

# ECB reference rates endpoint (Frankfurter v2).
BASE_URL = "https://api.frankfurter.dev/v2/providers/ecb/rates"

# Temporary problems worth retrying. 4xx errors (our own mistake) are not here.
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def _get_with_retries(
    params: dict[str, str],
    timeout: float,
    max_attempts: int,
    backoff_seconds: float,
) -> requests.Response:
    """GET the API, retrying temporary failures with exponential backoff.

    Retries on timeouts, connection errors and RETRY_STATUS_CODES. Other
    responses (including 4xx errors) are returned right away.

    Raises:
        requests.Timeout / requests.ConnectionError: if the last attempt fails.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_attempts:
                raise  # out of attempts: let the caller see the real error
            reason = type(exc).__name__
        else:
            if response.status_code not in RETRY_STATUS_CODES or attempt == max_attempts:
                return response
            reason = f"HTTP {response.status_code}"

        wait = backoff_seconds * 2 ** (attempt - 1)  # 1 s, 2 s, 4 s, ...
        logger.warning(
            "attempt %s/%s failed (%s), retrying in %.1fs", attempt, max_attempts, reason, wait
        )
        time.sleep(wait)

    raise RuntimeError("unreachable")  # the loop always returns or raises


def fetch_rates(
    base: str = "EUR",
    quotes: list[str] | None = None,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    timeout: float = 30.0,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
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
        timeout: Seconds to wait for each attempt.
        max_attempts: Total tries for temporary failures.
        backoff_seconds: Wait before the first retry; doubles each time.

    Raises:
        requests.HTTPError: if the API answers with a 4xx/5xx status code.
        requests.Timeout / requests.ConnectionError: if every attempt fails.
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

    response = _get_with_retries(params, timeout, max_attempts, backoff_seconds)
    response.raise_for_status()  # error answers become Python errors
    return response.json()


if __name__ == "__main__":
    import json

    data = fetch_rates(quotes=["USD", "GBP", "CHF", "JPY", "INR"])
    print(json.dumps(data, indent=2))