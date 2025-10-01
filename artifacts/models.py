from django.db import models
from django.conf import settings  # <-- use AUTH_USER_MODEL

def originals_path(instance, filename): return f"uploads/originals/{instance.user_id}/{filename}"
def processed_path(instance, filename): return f"uploads/processed/{instance.user_id}/{filename}"
def zips_path(instance, filename): return f"uploads/zips/{instance.user_id}/{filename}"
def geojson_path(instance, filename): return f"uploads/geojson/{instance.user_id}/{filename}"

class ProcessedResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='processed_results')

    original_image = models.ImageField(upload_to=originals_path)
    processed_image = models.ImageField(upload_to=processed_path)
    zip_file = models.FileField(upload_to=zips_path, null=True, blank=True)
    geojson_file = models.FileField(upload_to=geojson_path, null=True, blank=True)

    model_name = models.CharField(max_length=100, blank=True, default="")
    prompt = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Result #{self.pk} by {self.user} @ {self.created_at:%Y-%m-%d %H:%M}"
