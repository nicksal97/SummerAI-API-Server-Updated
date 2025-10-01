import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, permissions
from rest_framework.decorators import action

from .models import ProcessedResult
from .serializers import ProcessedResultSerializer

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id

class ProcessedResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/results/                       -> list current user's history
    GET  /api/results/{id}/download/<kind>/  -> download file (original|processed|zip|geojson)
    """
    serializer_class = ProcessedResultSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return ProcessedResult.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['get'], url_path=r'download/(?P<kind>original|processed|zip|geojson)')
    def download(self, request, pk=None, kind=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)

        field = {
            'original': obj.original_image,
            'processed': obj.processed_image,
            'zip': obj.zip_file,
            'geojson': obj.geojson_file,
        }.get(kind)

        if not field or not getattr(field, "name", ""):
            raise Http404(f"No {kind} file available.")

        abspath = Path(settings.MEDIA_ROOT) / field.name
        if not abspath.exists():
            raise Http404("File not found on server.")

        mime, _ = mimetypes.guess_type(str(abspath))
        resp = FileResponse(open(abspath, 'rb'), as_attachment=True, filename=abspath.name)
        if mime:
            resp.headers['Content-Type'] = mime
        return resp
