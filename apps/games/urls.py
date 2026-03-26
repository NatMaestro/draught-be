from django.urls import path
from . import views

urlpatterns = [
    path("", views.GameCreateView.as_view()),
    path("history/", views.GameHistoryView.as_view()),
    path("challenges/incoming/", views.ChallengeIncomingListView.as_view()),
    path("challenges/outgoing/", views.ChallengeOutgoingListView.as_view()),
    path("challenges/", views.ChallengeCreateView.as_view()),
    path(
        "challenges/<uuid:challenge_id>/accept/",
        views.ChallengeAcceptView.as_view(),
    ),
    path(
        "challenges/<uuid:challenge_id>/decline/",
        views.ChallengeDeclineView.as_view(),
    ),
    path(
        "challenges/<uuid:challenge_id>/cancel/",
        views.ChallengeCancelView.as_view(),
    ),
    path("<uuid:id>/", views.GameDetailView.as_view()),
    path("<uuid:id>/move/", views.MoveView.as_view()),
    path("<uuid:id>/ai-move/", views.AiMoveView.as_view()),
    path("<uuid:id>/legal-moves/", views.LegalMovesView.as_view()),
    path("<uuid:id>/resign/", views.ResignView.as_view()),
    path("<uuid:id>/undo/", views.UndoView.as_view()),
]
