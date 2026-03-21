# Generated manually — allow longer AI mode ids (expert, top_players, adaptive, …).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0004_add_is_local_2p"),
    ]

    operations = [
        migrations.AlterField(
            model_name="game",
            name="ai_difficulty",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
