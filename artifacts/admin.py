from django.contrib import admin
from .models import ProcessedResult

@admin.register(ProcessedResult)
class ProcessedResultAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "model_name", "created_at")
    list_filter = ("created_at", "model_name")
    search_fields = ("user__username", "model_name", "prompt")
