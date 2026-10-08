from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.OverviewView.as_view()),
    path("foods/", views.FoodListView.as_view()),
    path("recipes/", views.RecipeListView.as_view()),
    path("meals/", views.MealListView.as_view()),
    path("meals/<uuid:pk>/", views.MealDetailView.as_view()),
    path("ai/recognize/", views.RecognizeView.as_view()),
    path("ai/transcribe/", views.TranscribeView.as_view()),
    path("ai/analyze/", views.AnalyzeView.as_view()),
    path("ai/suggestions/", views.SuggestionsView.as_view()),
    path("recommendations/<uuid:pk>/review/", views.RecommendationReviewView.as_view()),
    path("lab-reviews/<uuid:pk>/review/", views.LabReviewDecisionView.as_view()),
    path("patients/<uuid:pk>/plans/", views.PlanView.as_view()),
    path("patients/<uuid:pk>/lab-trends/", views.LabTrendsView.as_view()),
    path("patients/<uuid:pk>/reports/", views.ReportListView.as_view()),
    path("patients/<uuid:pk>/reports/generate/", views.ReportGenerateView.as_view()),
    path("patients/<uuid:pk>/observations/", views.ObservationView.as_view()),
    path("reports/<uuid:pk>/release/", views.ReportReleaseView.as_view()),
]
