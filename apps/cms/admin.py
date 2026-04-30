from django.contrib import admin

from apps.cms.models import BlogPost, FaqItem


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "published", "featured", "published_at")
    list_filter = ("published", "featured")
    search_fields = ("title", "slug", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-featured", "-published_at", "-pk")


@admin.register(FaqItem)
class FaqItemAdmin(admin.ModelAdmin):
    list_display = ("question", "sort_order", "published")
    list_filter = ("published",)
    search_fields = ("question", "answer")
    list_editable = ("sort_order", "published")
