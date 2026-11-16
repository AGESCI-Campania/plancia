"""Fixture globali dei test."""
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def _senza_rate_limit_api(request):
    """Il rate limit dell'API conta le richieste su Redis per IP, condiviso tra test ed esecuzioni:
    qui si disattiva. I test del rate limit lo riattivano con il marker `rate_limit`."""
    if request.node.get_closest_marker("rate_limit"):
        yield
        return
    with mock.patch("apps.siteconfig.middleware._rate_limit_check", return_value=(True, 0)):
        yield
