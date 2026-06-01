from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("siteconfig", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="impostazioni",
            name="footer_testo",
            field=models.TextField(
                blank=True,
                help_text="Testo centrale del footer. Se vuoto usa il default.",
                verbose_name="testo footer",
            ),
        ),
        migrations.AddField(
            model_name="impostazioni",
            name="footer_link_label",
            field=models.CharField(
                default="campania.agesci.it",
                max_length=100,
                verbose_name="etichetta link footer",
            ),
        ),
        migrations.AddField(
            model_name="impostazioni",
            name="footer_link_url",
            field=models.URLField(
                default="https://campania.agesci.it",
                verbose_name="URL link footer",
            ),
        ),
    ]
