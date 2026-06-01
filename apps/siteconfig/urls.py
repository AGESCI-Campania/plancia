# apps/siteconfig/urls.py
from django.urls import path

from apps.siteconfig import views

app_name = "siteconfig"

urlpatterns = [
    path("", views.ImpostazioniView.as_view(), name="impostazioni"),
    path("import/<str:tracciato>/", views.LanciaImportView.as_view(), name="lancia_import"),
    path("mail/<str:chiave>/", views.MailTemplateEditView.as_view(), name="mail_template_edit"),
    path("mail/<str:chiave>/importa/", views.MailTemplateImportaView.as_view(), name="mail_template_importa"),
    path("mail/<str:chiave>/elimina/", views.MailTemplateDeleteView.as_view(), name="mail_template_elimina"),
]
