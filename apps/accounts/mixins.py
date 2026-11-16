# apps/accounts/mixins.py
"""Mixin di autorizzazione riutilizzabili nelle viste Plancia.

Il controllo avviene PRIMA di eseguire la vista: un 403 sollevato dopo `super().dispatch()`
arriverebbe a operazione già compiuta (POST eseguite comunque).
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RuoloRequiredMixin(LoginRequiredMixin):
    """Richiede che l'utente abbia uno dei ruoli indicati in `ruoli_ammessi`."""

    ruoli_ammessi: tuple[str, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        utente = request.user
        if (
            utente.is_authenticated
            and self.ruoli_ammessi
            and utente.ruolo not in self.ruoli_ammessi
            and not utente.is_superuser
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class StaffPlanciaRequiredMixin(LoginRequiredMixin):
    """Richiede Admin, Segreteria o Incaricato EG."""

    def dispatch(self, request, *args, **kwargs):
        utente = request.user
        if utente.is_authenticated and not (utente.is_staff_plancia or utente.is_superuser):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
