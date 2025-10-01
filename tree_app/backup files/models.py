from django.db import models


class OutputRun(models.Model):
    """
    One processing run (metadata only, files live under /static).
    """
    run_id = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional label / model metadata
    label = models.CharField(max_length=128, blank=True)
    model = models.CharField(max_length=32, blank=True)
    model_name = models.CharField(max_length=256, blank=True)

    # Paths (stored as strings so we don't couple to storage backends)
    input_dir = models.CharField(max_length=512, blank=True)
    result_dir = models.CharField(max_length=512, blank=True)
    zip_path = models.CharField(max_length=512, blank=True)
    outputs_zip_path = models.CharField(max_length=512, blank=True)
    geojson_path = models.CharField(max_length=512, blank=True)

    # Image URL lists
    input_images = models.JSONField(default=list, blank=True)
    output_images = models.JSONField(default=list, blank=True)

    # Convenience thumbnail URL
    thumbnail = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        title = self.label or self.run_id
        return f"{title} — {self.created_at:%Y-%m-%d %H:%M:%S}"
