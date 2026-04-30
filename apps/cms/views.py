from drf_spectacular.utils import extend_schema
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny

from apps.cms.models import BlogPost, FaqItem
from apps.cms.serializers import (
    BlogPostDetailSerializer,
    BlogPostListSerializer,
    FaqItemSerializer,
)


class BlogPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Public landing blog."""

    authentication_classes = []
    permission_classes = [AllowAny]
    queryset = BlogPost.objects.filter(published=True)
    pagination_class = None
    lookup_field = "slug"
    lookup_value_regex = r"[a-zA-Z0-9\-]+"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BlogPostDetailSerializer
        return BlogPostListSerializer

    @extend_schema(summary="Blog index", tags=["Landing CMS"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Blog post", tags=["Landing CMS"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


@extend_schema(summary="FAQ list", tags=["Landing CMS"])
class FaqListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    queryset = FaqItem.objects.filter(published=True)
    pagination_class = None
    serializer_class = FaqItemSerializer
