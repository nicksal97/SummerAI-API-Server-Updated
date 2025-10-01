from rest_framework import serializers
from .models import ProcessedResult

class ProcessedResultSerializer(serializers.ModelSerializer):
    original_url = serializers.SerializerMethodField()
    processed_url = serializers.SerializerMethodField()
    zip_url = serializers.SerializerMethodField()
    geojson_url = serializers.SerializerMethodField()

    class Meta:
        model = ProcessedResult
        fields = [
            'id', 'created_at', 'model_name', 'prompt',
            'original_url', 'processed_url', 'zip_url', 'geojson_url',
        ]

    def get_original_url(self, obj):
        return obj.original_image.url if obj.original_image else None

    def get_processed_url(self, obj):
        return obj.processed_image.url if obj.processed_image else None

    def get_zip_url(self, obj):
        return obj.zip_file.url if obj.zip_file else None

    def get_geojson_url(self, obj):
        return obj.geojson_file.url if obj.geojson_file else None
