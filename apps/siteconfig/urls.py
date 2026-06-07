# apps/siteconfig/urls.py
from django.urls import path

from apps.siteconfig import views

app_name = "siteconfig"

urlpatterns = [
    path("", views.ImpostazioniView.as_view(), name="impostazioni"),
    path("test-email/", views.TestEmailView.as_view(), name="test_email"),
    path("pagine/<str:slug>/", views.PaginaStaticaEditView.as_view(), name="pagina_edit"),
    path("gmail-smtp/oauth/", views.GmailSMTPOAuthInitView.as_view(), name="gmail_smtp_oauth_init"),
    path("gmail-smtp/oauth/callback/", views.GmailSMTPOAuthCallbackView.as_view(), name="gmail_smtp_oauth_callback"),
    path("gmail-smtp/oauth/disconnect/", views.GmailSMTPOAuthDisconnectView.as_view(), name="gmail_smtp_oauth_disconnect"),
    path("import/<str:tracciato>/", views.LanciaImportView.as_view(), name="lancia_import"),
    path("mail/<str:chiave>/", views.MailTemplateEditView.as_view(), name="mail_template_edit"),
    path("mail/<str:chiave>/importa/", views.MailTemplateImportaView.as_view(), name="mail_template_importa"),
    path("mail/<str:chiave>/copia/", views.MailTemplateCopiaView.as_view(), name="mail_template_copia"),
    path("mail/<str:chiave>/elimina/", views.MailTemplateDeleteView.as_view(), name="mail_template_elimina"),
    path("mail/upload-immagine/", views.MailTemplateImageUploadView.as_view(), name="mail_image_upload"),
]
