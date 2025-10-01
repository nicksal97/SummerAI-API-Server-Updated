from django.urls import path
from tree_app import views

urlpatterns = [
    path("", views.index, name="index"),

    # auth
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),
    path("signup/", views.signup_request, name="signup"),

    # model management
    path("model/upload/", views.model_upload, name="model_upload"),
    path("model-upload1/", views.model_upload1, name="model_upload1"),
    path("model/delete/", views.delete_file, name="delete_file"),

    # geojson helpers
    path("geojson/path/", views.geo_json_path, name="geo_json_path"),
    path("api/geojson/latest", views.geojson_latest, name="geojson_latest"),

    # history
    path("history/", views.history_page, name="history_page"),
    path("api/runs", views.history_runs, name="history_runs"),
    path("api/runs/<str:run_id>", views.history_run_detail, name="history_run_detail"),
]
