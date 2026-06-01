# Generated manually 2026-05-31
# Sostituisce FK diario con FK valutazione su AssegnazionePGV.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0001_initial"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="assegnazionepgv",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="assegnazionepgv",
            name="diario",
        ),
        migrations.AddField(
            model_name="assegnazionepgv",
            name="valutazione",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assegnazioni_pgv",
                to="evaluations.valutazione",
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="assegnazionepgv",
            unique_together={("valutazione", "pgv")},
        ),
    ]
