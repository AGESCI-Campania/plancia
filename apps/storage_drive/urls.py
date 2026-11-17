from django.urls import path

from apps.storage_drive import views

app_name = "storage_drive"

urlpatterns = [
    path("oauth/callback/", views.DriveOAuthCallbackView.as_view(), name="oauth_callback"),
]
