from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("siteconfig", "0003_footer_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="footerlink",
            name="etichetta",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Se vuota usa il nome del tipo (es. 'Sito web').",
                max_length=20,
                verbose_name="etichetta",
            ),
        ),
    ]
