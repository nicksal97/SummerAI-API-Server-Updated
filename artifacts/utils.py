from pathlib import Path
from .models import ProcessedResult

def save_processed_result_for_user(
    *, user, original_abs_path, processed_abs_path=None,
    zip_abs_path=None, geojson_abs_path=None, model_name="", prompt=""
):
    result = ProcessedResult(user=user, model_name=model_name, prompt=prompt)

    def attach(field, abspath):
        if abspath and Path(abspath).exists():
            with open(abspath, "rb") as f:
                field.save(Path(abspath).name, f, save=False)

    attach(result.original_image, original_abs_path)
    attach(result.processed_image, processed_abs_path)
    attach(result.zip_file, zip_abs_path)
    attach(result.geojson_file, geojson_abs_path)

    result.save()
    return result
