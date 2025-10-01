from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProcessedResultViewSet

router = DefaultRouter()
router.register(r'', ProcessedResultViewSet, basename='artifacts')

urlpatterns = [
    path('', include(router.urls)),
]
