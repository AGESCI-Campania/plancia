from django.db import migrations, models

from apps.editions.models import CARTELLA_DIARIO_FORMAT_DEFAULT


class Migration(migrations.Migration):

    dependencies = [
        ("editions", "0002_edizione_evento_drive"),
    ]

    operations = [
        migrations.AddField(
            model_name="edizione",
            name="cartella_diario_format",
            field=models.CharField(
                blank=True,
                default=CARTELLA_DIARIO_FORMAT_DEFAULT,
                help_text=(
                    "Variabili: {id_univoco} {edizione} {nome_gruppo} {nome_zona} "
                    "{nome_reparto} {nome_squadriglia} {specialita}. "
                    "{id_univoco} è obbligatorio."
                ),
                max_length=300,
                verbose_name="formato nome cartella diario",
            ),
        ),
    ]
