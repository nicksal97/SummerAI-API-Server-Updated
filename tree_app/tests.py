from django.test import TestCase

# Create your tests here.
def convert_to_txt(filename):
    # Check if the filename ends with a known image file extension
    image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
    for ext in image_extensions:
        if filename.endswith(ext):
            # Remove the extension and add ".txt"
            return filename[:-len(ext)] + ".txt"
    # If the filename doesn't end with any known image file extension, just add ".txt"
    return filename + ".txt"

# Example filename
filename = "input.png"
# Convert to .txt
txt_filename = convert_to_txt(filename)
print("Converted filename:", txt_filename)
