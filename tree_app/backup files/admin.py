from django.contrib import admin

# Make admin robust even if migrations/models aren’t ready yet
try:
    from .models import OutputRun
except Exception:
    OutputRun = None  # type: ignore


if OutputRun is not None:
    @admin.register(OutputRun)
    class OutputRunAdmin(admin.ModelAdmin):
        list_display = ("run_id", "label", "created_at", "model", "model_name")
        search_fields = ("run_id", "label", "model", "model_name")
        ordering = ("-created_at",)
