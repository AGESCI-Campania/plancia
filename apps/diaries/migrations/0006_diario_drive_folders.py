from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diaries", "0005_relazione_finale_stato"),
    ]

    operations = [
        migrations.AddField(
            model_name="diario",
            name="drive_folder_allegati_id",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="ID cartella Drive allegati (diario)",
            ),
        ),
        migrations.AddField(
            model_name="diario",
            name="drive_folder_output_id",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="ID cartella Drive output (diario)",
            ),
        ),
    ]
