# Generated manually for CMS app

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BlogPost",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(db_index=True, max_length=180, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("excerpt", models.TextField(blank=True)),
                ("body", models.TextField(help_text="Separate paragraphs with a blank line. No HTML required.")),
                ("featured", models.BooleanField(default=False)),
                ("published", models.BooleanField(db_index=True, default=False)),
                ("published_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "read_time_label",
                    models.CharField(
                        blank=True,
                        help_text='Shown as read time e.g. "5 min read". Leave blank for an automatic estimate.',
                        max_length=40,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-featured", "-published_at", "-pk"],
            },
        ),
        migrations.CreateModel(
            name="FaqItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("question", models.CharField(max_length=500)),
                ("answer", models.TextField()),
                ("sort_order", models.PositiveSmallIntegerField(db_index=True, default=0)),
                ("published", models.BooleanField(db_index=True, default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["sort_order", "pk"],
                "verbose_name": "FAQ item",
                "verbose_name_plural": "FAQ items",
            },
        ),
        migrations.AddIndex(
            model_name="blogpost",
            index=models.Index(fields=["published", "-published_at"], name="cms_blogpos_publish_Idx"),
        ),
    ]
