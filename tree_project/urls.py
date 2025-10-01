"""tree_project URL Configuration"""

from django.contrib import admin
from django.urls import path
from tree_app import views  # <-- change 'tree_app' here if your app has a different name

# Serve /static/ in development so the browser can fetch images / zip / geojson
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # main workflow endpoints used by your frontend
    path("", views.index, name="index"),
    path("signup/", views.signup_request, name="signup"),
    path("login/", views.login_request, name="login"),
    path("logout/", views.logout_request, name="logout"),

    path("model-upload/", views.model_upload, name="model-upload"),
    path("model-upload1/", views.model_upload1, name="model_upload1"),
    path("delete-file/", views.delete_file, name="delete-file"),
    path("geo-json-path/", views.geo_json_path, name="geo-json-path"),
]

# In development, serve the /static/ folder directly (needed for your images/zip/geojson)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
