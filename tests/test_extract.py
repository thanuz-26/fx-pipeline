"""Unit tests for the extract step (a fake requests.get, no real API calls)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from fx_pipeline.extract import BASE_URL, fetch_rates

PAYLOAD = [{"date": "2026-10-30", "base": "EUR", "quote": "USD", "rate": 1.1}]


def make_response(status: int = 200, payload: Any = None) -> MagicMock:
    """A fake HTTP response; raise_for_status() raises for 4xx/5xx like the real one."""
    response = MagicMock(status_code=status)
    response.json.return_value = payload if payload is not None else PAYLOAD
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status}", response=response
        )
    return response


def test_default_request_sends_base_and_timeout() -> None:
    with patch("fx_pipeline.extract.requests.get", return_value=make_response()) as get:
        assert fetch_rates() == PAYLOAD
    get.assert_called_once_with(BASE_URL, params={"base": "EUR"}, timeout=30.0)


def test_quotes_are_joined_with_commas_and_single_date_is_sent() -> None:
    with patch("fx_pipeline.extract.requests.get", return_value=make_response()) as get:
        fetch_rates(quotes=["USD", "GBP"], date="2026-10-30")
    params = get.call_args.kwargs["params"]
    assert params == {"base": "EUR", "quotes": "USD,GBP", "date": "2026-10-30"}


def test_range_is_sent_as_from_and_to() -> None:
    with patch("fx_pipeline.extract.requests.get", return_value=make_response()) as get:
        fetch_rates(start_date="2026-10-26", end_date="2026-10-30")
    params = get.call_args.kwargs["params"]
    assert params["from"] == "2026-10-26"
    assert params["to"] == "2026-10-30"


def test_retries_timeout_then_succeeds() -> None:
    effects = [requests.Timeout(), requests.Timeout(), make_response()]
    with patch("fx_pipeline.extract.requests.get", side_effect=effects) as get:
        assert fetch_rates(backoff_seconds=0) == PAYLOAD
    assert get.call_count == 3


def test_retries_server_error_then_succeeds() -> None:
    effects = [make_response(503), make_response()]
    with patch("fx_pipeline.extract.requests.get", side_effect=effects) as get:
        assert fetch_rates(backoff_seconds=0) == PAYLOAD
    assert get.call_count == 2


def test_gives_up_after_max_attempts_on_timeout() -> None:
    with patch("fx_pipeline.extract.requests.get", side_effect=requests.Timeout()) as get:
        with pytest.raises(requests.Timeout):
            fetch_rates(backoff_seconds=0)
    assert get.call_count == 3


def test_gives_up_on_persistent_server_error() -> None:
    with patch("fx_pipeline.extract.requests.get", return_value=make_response(503)) as get:
        with pytest.raises(requests.HTTPError):
            fetch_rates(backoff_seconds=0)
    assert get.call_count == 3


def test_client_error_is_not_retried() -> None:
    with patch("fx_pipeline.extract.requests.get", return_value=make_response(422)) as get:
        with pytest.raises(requests.HTTPError):
            fetch_rates(quotes=["ABC"], backoff_seconds=0)
    assert get.call_count == 1  # a 4xx is our own mistake: asking again can't help


def test_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        fetch_rates(max_attempts=0)