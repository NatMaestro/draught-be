from django.db import models
from django.utils import timezone


class BlogPost(models.Model):
    """
    Landing-site blog articles. Paragraphs use blank lines inside ``body``.
    Manage via Django Admin; public site reads `/api/cms/blog/`.
    """

    slug = models.SlugField(max_length=180, unique=True, db_index=True)
    title = models.CharField(max_length=300)
    excerpt = models.TextField(blank=True)
    body = models.TextField(
        help_text="Separate paragraphs with a blank line. No HTML required.",
    )
    featured = models.BooleanField(
        default=False,
        help_text="Pins this post above others on equivalent dates when sorted.",
    )
    published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Displayed publish date on the landing site.",
    )
    read_time_label = models.CharField(
        max_length=40,
        blank=True,
        help_text='Shown as read time e.g. "5 min read". Leave blank for an automatic estimate.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-featured", "-published_at", "-pk"]
        indexes = [
            models.Index(fields=["published", "-published_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if self.published and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class FaqItem(models.Model):
    """Landing FAQ entries (published only on the public API)."""

    question = models.CharField(max_length=500)
    answer = models.TextField()
    sort_order = models.PositiveSmallIntegerField(default=0, db_index=True)
    published = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "FAQ item"
        verbose_name_plural = "FAQ items"

    def __str__(self) -> str:
        return self.question[:60]
