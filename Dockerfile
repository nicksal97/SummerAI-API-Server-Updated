FROM python:3.8

# Allows docker to cache installed dependencies between builds
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Mounts the application code to the image
COPY . code
WORKDIR /code

EXPOSE 8001

# runs the production server
ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8001"]