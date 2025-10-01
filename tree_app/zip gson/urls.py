from django.urls import path
from tree_app import views

urlpatterns = [
    # Home / processing
    path("", views.index, name="index"),

    # Auth
    path("signup/", views.signup_request, name="signup"),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),

    # Model mgmt
    path("model-upload/", views.model_upload, name="model-upload"),
    path("model-upload1/", views.model_upload1, name="model_upload1"),
    path("delete-file/", views.delete_file, name="delete-file"),

    # History APIs used by React
    path("api/runs", views.runs_history, name="runs_history"),
    path("api/runs/<str:run_id>", views.runs_history_detail, name="runs_history_detail"),

    # GeoJSON helper
    path("geo-json-path/", views.geo_json_path, name="geo-json-path"),
]
