from django.contrib import admin
from .models import OutputRun

@admin.register(OutputRun)
class OutputRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "created_at", "label", "model", "model_name")
    search_fields = ("run_id", "label", "model", "model_name")
    list_filter = ("model", "created_at")
