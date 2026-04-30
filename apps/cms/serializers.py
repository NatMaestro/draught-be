from rest_framework import serializers

from apps.cms.models import BlogPost, FaqItem


def paragraphs_from_body(body: str) -> list[str]:
    text = body.replace("\r\n", "\n")
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def read_time_from_body(body: str) -> str:
    words = len(body.replace("\n", " ").split())
    mins = max(1, round(words / 200))
    return f"{mins} min read"


class BlogPostListSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    readTime = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = ("slug", "title", "excerpt", "date", "readTime", "featured")

    def get_date(self, obj: BlogPost) -> str | None:
        if obj.published_at is None:
            return None
        return obj.published_at.date().isoformat()

    def get_readTime(self, obj: BlogPost) -> str:
        if (obj.read_time_label or "").strip():
            return (obj.read_time_label or "").strip()
        return read_time_from_body(obj.body)


class BlogPostDetailSerializer(BlogPostListSerializer):
    paragraphs = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = BlogPostListSerializer.Meta.fields + ("paragraphs",)

    def get_paragraphs(self, obj: BlogPost) -> list[str]:
        return paragraphs_from_body(obj.body)


class FaqItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqItem
        fields = ("id", "question", "answer")
