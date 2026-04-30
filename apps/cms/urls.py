from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.cms.views import BlogPostViewSet, FaqListView

router = DefaultRouter(trailing_slash=True)
router.register("blog", BlogPostViewSet, basename="cms-blog")

urlpatterns = [
    path("", include(router.urls)),
    path("faq/", FaqListView.as_view(), name="cms-faq-list"),
]
