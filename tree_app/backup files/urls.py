from django.urls import path
from tree_app import views

urlpatterns = [
    path("", views.index, name="index"),

    # auth
    path("signup/", views.signup_request, name="signup"),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),

    # model management
    path("model-upload/", views.model_upload, name="model-upload"),
    path("model-upload1/", views.model_upload1, name="model-upload1"),
    path("delete-file/", views.delete_file, name="delete-file"),

    # geojson
    path("geo-json-path/", views.geo_json_path, name="geo-json-path"),

    # history – just list static/zip files so UI can show download buttons
    path("history/", views.history_page, name="history_page"),
    path("api/zips", views.zips_history, name="zips_history"),
    path("api/runs", views.zips_history, name="api_runs_compat"),  # old UI compatibility
]
