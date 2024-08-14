import os

# Filename with extension
filename_with_extension = "tree_.image.zip"

# Get the filename without extension
filename_without_extension = os.path.splitext(filename_with_extension)

print(filename_without_extension)
