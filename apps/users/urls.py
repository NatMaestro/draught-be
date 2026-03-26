from django.urls import path
from . import views

urlpatterns = [
    path("profile/", views.ProfileView.as_view()),
    path("search/", views.UserSearchView.as_view()),
    path("leaderboard/", views.LeaderboardView.as_view()),
]
