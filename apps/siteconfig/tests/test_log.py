"""Email agli amministratori dal logging: niente 503 della manutenzione, niente doppioni."""

import logging.config

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils.log import DEFAULT_LOGGING, configure_logging, log_response


@pytest.fixture
def logging_configurato(settings):
    # Come Django all'avvio: prima la configurazione di default, poi LOGGING
    settings.ADMINS = ["admin@example.org"]
    logging.config.dictConfig(DEFAULT_LOGGING)
    logging.config.dictConfig(settings.LOGGING)
    yield
    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)


@pytest.mark.parametrize(("stato", "email"), [(503, 0), (500, 1)])
def test_email_agli_amministratori(logging_configurato, mailoutbox, stato, email):
    request = RequestFactory().get("/api/v1/me")
    log_response("Errore: %s", request.path, response=HttpResponse(status=stato), request=request)
    assert len(mailoutbox) == email  # 503 mai, 500 una sola volta (non doppia)
