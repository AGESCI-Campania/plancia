from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"

    def ready(self):
        try:
            from anymail.signals import post_send, tracking

            from apps.notifications.webhooks import handle_post_send, handle_tracking
            post_send.connect(handle_post_send)
            tracking.connect(handle_tracking)
        except ImportError:
            pass  # anymail non installato o non configurato
