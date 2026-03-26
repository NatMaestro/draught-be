import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0008_game_challenge_and_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamechallenge",
            name="result_game",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="challenge_created_from",
                to="games.game",
            ),
        ),
    ]
