from django.urls import path
from . import views

urlpatterns = [
    path("join/", views.JoinMatchmakingView.as_view()),
    path("cancel/", views.CancelMatchmakingView.as_view()),
    path("ready/", views.MatchReadyView.as_view()),
]
