FROM python:3.11-slim

# System deps:
#  - libgl1 / libglib2.0-0: required by OpenCV (opencv-python-headless still
#    links libgthread/libGL at runtime on slim images).
#  - build-essential + cmake: insightface compiles native extensions on install.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Bind $PORT when the platform provides one (Render injects it), else 7860
# (Hugging Face Spaces expects 7860). docker-compose overrides this command to
# use port 8000 for local dev.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
