# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import LoginEvent, Nomina, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Dati personali"), {"fields": ("username", "first_name", "last_name")}),
        (_("Ruolo Plancia"), {"fields": ("ruolo", "mfa_obbligatoria", "socio")}),
        (
            _("Permessi"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Date importanti"), {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "ruolo", "password1", "password2"),
            },
        ),
    )
    list_display = ("email", "ruolo", "socio", "mfa_obbligatoria", "is_active")
    list_filter = ("ruolo", "is_active", "mfa_obbligatoria")
    search_fields = ("email", "username", "socio__cognome", "socio__nome")
    ordering = ("email",)
    autocomplete_fields = ["socio"]


@admin.register(Nomina)
class NominaAdmin(admin.ModelAdmin):
    list_display = ("ruolo", "socio", "utente", "nominato_da", "edizione", "creato_at")
    list_filter = ("ruolo", "edizione")
    search_fields = ("socio__cognome", "socio__nome", "utente__email")
    autocomplete_fields = ["socio", "utente", "nominato_da"]
    raw_id_fields = ["edizione"]
    date_hierarchy = "creato_at"


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("utente", "esito", "provider", "ip", "creato_at")
    list_filter = ("esito", "provider")
    search_fields = ("utente__email", "ip")
    readonly_fields = ("utente", "esito", "provider", "ip", "user_agent", "creato_at")
    date_hierarchy = "creato_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
