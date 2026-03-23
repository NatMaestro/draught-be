from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0005_alter_game_ai_difficulty"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="time_control_sec",
            field=models.PositiveIntegerField(
                default=600,
                help_text="Initial bank per player in seconds (e.g. 600 = 10 minutes).",
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="p1_time_remaining_sec",
            field=models.FloatField(default=600.0),
        ),
        migrations.AddField(
            model_name="game",
            name="p2_time_remaining_sec",
            field=models.FloatField(default=600.0),
        ),
        migrations.AddField(
            model_name="game",
            name="turn_started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the current turn began; active player's clock runs from here.",
                null=True,
            ),
        ),
    ]
