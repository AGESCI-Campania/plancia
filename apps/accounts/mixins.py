# apps/accounts/mixins.py
"""Mixin di autorizzazione riutilizzabili nelle viste Plancia."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import Ruolo


class RuoloRequiredMixin(LoginRequiredMixin):
    """Richiede che l'utente abbia uno dei ruoli indicati in `ruoli_ammessi`."""

    ruoli_ammessi: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and self.ruoli_ammessi:
            if request.user.ruolo not in self.ruoli_ammessi and not request.user.is_superuser:
                raise PermissionDenied
        return response


class StaffPlanciaRequiredMixin(LoginRequiredMixin):
    """Richiede Admin, Segreteria o Incaricato EG."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated:
            if not (request.user.is_staff_plancia or request.user.is_superuser):
                raise PermissionDenied
        return response
