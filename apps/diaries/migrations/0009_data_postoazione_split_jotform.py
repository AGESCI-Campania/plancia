"""Migrazione dati:
- Divide PostoAzione.descrizione in chi + cosa (separatore ' — ')
- Pulisce link_esterno su Impresa che puntano a jotform.com
"""
from django.db import migrations


def split_posti_azione(apps, schema_editor):
    PostoAzione = apps.get_model("diaries", "PostoAzione")
    for pa in PostoAzione.objects.filter(chi="", cosa="").exclude(descrizione=""):
        if " — " in pa.descrizione:
            chi, cosa = pa.descrizione.split(" — ", 1)
            pa.chi = chi.strip()[:200]
            pa.cosa = cosa.strip()[:300]
        else:
            pa.cosa = pa.descrizione[:300]
        pa.save(update_fields=["chi", "cosa"])


def pulisci_link_jotform(apps, schema_editor):
    Impresa = apps.get_model("diaries", "Impresa")
    Impresa.objects.filter(
        link_esterno__startswith="https://www.jotform.com"
    ).update(link_esterno="")


class Migration(migrations.Migration):
    dependencies = [
        ("diaries", "0008_nuovi_campi_moduli"),
    ]

    operations = [
        migrations.RunPython(split_posti_azione, migrations.RunPython.noop),
        migrations.RunPython(pulisci_link_jotform, migrations.RunPython.noop),
    ]
