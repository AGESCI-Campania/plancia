"""I mixin di permesso bloccano la vista prima che venga eseguita."""
import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from apps.accounts.mixins import RuoloRequiredMixin, StaffPlanciaRequiredMixin
from apps.accounts.models import Ruolo, User

pytestmark = pytest.mark.django_db


class _VistaAdmin(RuoloRequiredMixin, View):
    ruoli_ammessi = (Ruolo.ADMIN,)
    eseguita = False

    def post(self, request):
        type(self).eseguita = True
        return HttpResponse("ok")


class _VistaStaff(StaffPlanciaRequiredMixin, View):
    eseguita = False

    def post(self, request):
        type(self).eseguita = True
        return HttpResponse("ok")


@pytest.mark.parametrize("vista", [_VistaAdmin, _VistaStaff])
def test_ruolo_non_ammesso_non_esegue_la_post(vista):
    vista.eseguita = False
    utente = User.objects.create_user(username="c@t.it", email="c@t.it", password="x", ruolo=Ruolo.CSQ)
    request = RequestFactory().post("/")
    request.user = utente
    with pytest.raises(PermissionDenied):
        vista.as_view()(request)
    assert vista.eseguita is False
