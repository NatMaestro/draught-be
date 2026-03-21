from django.urls import path
from . import views

urlpatterns = [
    path("", views.GameCreateView.as_view()),
    path("history/", views.GameHistoryView.as_view()),
    path("<uuid:id>/", views.GameDetailView.as_view()),
    path("<uuid:id>/move/", views.MoveView.as_view()),
    path("<uuid:id>/ai-move/", views.AiMoveView.as_view()),
    path("<uuid:id>/legal-moves/", views.LegalMovesView.as_view()),
    path("<uuid:id>/resign/", views.ResignView.as_view()),
    path("<uuid:id>/undo/", views.UndoView.as_view()),
]
