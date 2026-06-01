from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        # Connette i signal allauth → LoginEvent (docs sez. 12)
        from . import signals  # noqa: F401
