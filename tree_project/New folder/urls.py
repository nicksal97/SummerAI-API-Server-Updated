"""tree_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from tree_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),

    path('signup/', views.signup_request, name='signup'),
    path('login/', views.login_request, name='login'),
    path('model-upload/', views.model_upload, name='model-upload'),
    path('model-upload1/', views.model_upload1, name='model_upload1'),
    path('logout/', views.logout_request, name='logout'),
    path('delete-file/', views.delete_file, name='delete-file'),
    path('geo-json-path/', views.geo_json_path, name='geo-json-path'),
]
