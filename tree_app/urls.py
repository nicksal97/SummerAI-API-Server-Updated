from django.urls import path
from . import views

urlpatterns = [
    # page
    path("", views.index, name="index"),

    # auth
    path("signup", views.signup_request, name="signup"),
    path("login", views.login_request, name="login"),
    path("logout", views.logout_request, name="logout"),

    # model mgmt
    path("api/model_upload1", views.model_upload1, name="model_upload1"),
    path("api/model_upload", views.model_upload, name="model_upload"),
    path("api/delete_model_file", views.delete_file, name="delete_model_file"),

    # geojson (baseline structure)
    path("api/geojson", views.geo_json_path, name="geo_json_path"),

    # history — simple zip list + aliases
    path("api/zips", views.zips_history, name="zips_history"),
    path("api/zips/", views.zips_history),
    path("api/history", views.zips_history),
    path("api/history/", views.zips_history),
    path("api/zip_history", views.zips_history),
    path("api/zip_history/", views.zips_history),

    # optional plain-text list + download-all
    path("api/zips.txt", views.zips_plain),
    path("api/zips/download_all", views.download_all_zips, name="download_all_zips"),
]
