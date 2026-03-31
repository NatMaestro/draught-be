import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0009_gamechallenge_result_game"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("p1_wins", models.PositiveSmallIntegerField(default=0)),
                ("p2_wins", models.PositiveSmallIntegerField(default=0)),
                (
                    "target_wins",
                    models.PositiveSmallIntegerField(
                        default=5,
                        help_text="Mini-games needed to win the match (e.g. 5).",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("finished", "Finished")],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                ("is_raw", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "match_winner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="match_victories",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "games_matchsession",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="game",
            name="match_session",
            field=models.ForeignKey(
                blank=True,
                help_text="When set, board wins feed this match until target_wins is reached.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="games",
                to="games.matchsession",
            ),
        ),
        migrations.AddField(
            model_name="gamechallenge",
            name="is_match",
            field=models.BooleanField(
                default=False,
                help_text="First-to-five mini-games when the challenge is accepted.",
            ),
        ),
    ]
