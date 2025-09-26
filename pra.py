import os
import zipfile

def remove_tif_file(folder_path):
    """Remove the only .tif file in the given folder."""
    try:
        # List all files in the folder
        files = [f for f in os.listdir(folder_path) if f.endswith('.tif')]
        for file in files:
            file_path = os.path.join(folder_path, file)
            print(file_path)
            os.remove(file_path)
    except Exception as e:
        print(f"Error: {e}")


def zip_folder(folder_path, zip_file_path):
    """Create a ZIP file of the given folder."""
    try:
        # Create a zip file at the specified location
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk the folder and add all files to the zip file
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, folder_path))
        print(f"Folder successfully zipped into: {zip_file_path}")
    except Exception as e:
        print(f"Error: {e}")


# Example usage
folder_path = 'static/input_img/2024-12-17_15-47-45'  # Replace with your folder path
remove_tif_file(folder_path)

zip_folder(folder_path, f'static/input_img/2024-12-17_15-47-45.zip')


