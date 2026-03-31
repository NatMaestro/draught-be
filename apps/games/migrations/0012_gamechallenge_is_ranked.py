from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0011_alter_game_time_control_sec_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamechallenge",
            name="is_ranked",
            field=models.BooleanField(
                default=False,
                help_text="When True, the game from this invite uses Elo (per board or per match).",
            ),
        ),
    ]
