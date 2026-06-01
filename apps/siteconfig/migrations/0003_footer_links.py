from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("siteconfig", "0002_impostazioni_footer"),
    ]

    operations = [
        migrations.CreateModel(
            name="FooterLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(
                    blank=True,
                    choices=[
                        ("sito_web", "Sito web"),
                        ("email", "Email"),
                        ("facebook", "Facebook"),
                        ("instagram", "Instagram"),
                        ("tiktok", "TikTok"),
                    ],
                    default="",
                    max_length=20,
                )),
                ("url", models.CharField(blank=True, default="", max_length=500, verbose_name="URL")),
                ("ordine", models.PositiveSmallIntegerField(default=0)),
                (
                    "impostazioni",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="footer_links",
                        to="siteconfig.impostazioni",
                    ),
                ),
            ],
            options={
                "verbose_name": "Link footer",
                "verbose_name_plural": "Link footer",
                "ordering": ["ordine", "pk"],
            },
        ),
        migrations.RemoveField(model_name="impostazioni", name="footer_link_label"),
        migrations.RemoveField(model_name="impostazioni", name="footer_link_url"),
    ]
