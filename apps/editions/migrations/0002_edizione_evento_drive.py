# Generated manually 2026-05-31
# - data_evento → data_evento_inizio + data_evento_fine
# - aggiunge evento_comune, evento_localita
# - rinomina drive_folder_foto_id → drive_folder_allegati_id

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("editions", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="edizione",
            old_name="drive_folder_foto_id",
            new_name="drive_folder_allegati_id",
        ),
        migrations.RemoveField(
            model_name="edizione",
            name="data_evento",
        ),
        migrations.AddField(
            model_name="edizione",
            name="data_evento_inizio",
            field=models.DateField(blank=True, null=True, verbose_name="inizio evento Guidoncini Verdi"),
        ),
        migrations.AddField(
            model_name="edizione",
            name="data_evento_fine",
            field=models.DateField(blank=True, null=True, verbose_name="fine evento Guidoncini Verdi"),
        ),
        migrations.AddField(
            model_name="edizione",
            name="evento_comune",
            field=models.CharField(blank=True, max_length=120, verbose_name="comune"),
        ),
        migrations.AddField(
            model_name="edizione",
            name="evento_localita",
            field=models.CharField(blank=True, max_length=200, verbose_name="località (opzionale)"),
        ),
        migrations.AlterField(
            model_name="edizione",
            name="drive_folder_allegati_id",
            field=models.CharField(blank=True, max_length=200, verbose_name="ID cartella Drive allegati"),
        ),
    ]
