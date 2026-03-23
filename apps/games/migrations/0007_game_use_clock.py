# Generated manually for use_clock flag.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0006_game_clock_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="use_clock",
            field=models.BooleanField(
                default=True,
                help_text="When False, no time limits and no clock deductions.",
            ),
        ),
    ]
