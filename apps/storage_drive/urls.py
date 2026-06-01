from django.urls import path

from apps.storage_drive import views

app_name = "storage_drive"

urlpatterns = [
    path("oauth/init/", views.DriveOAuthInitView.as_view(), name="oauth_init"),
    path("oauth/callback/", views.DriveOAuthCallbackView.as_view(), name="oauth_callback"),
    path("cartelle/", views.DriveFolderListView.as_view(), name="folder_list"),
    path("cartelle/crea/", views.DriveCartellaCreaView.as_view(), name="folder_create"),
    path("edizione/<int:pk>/cartelle/", views.DriveEdizioneFolderUpdateView.as_view(), name="edizione_folder_update"),
]
