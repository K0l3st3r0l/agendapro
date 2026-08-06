FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --reload es una bandera de desarrollo: levanta un watcher de archivos, gasta
# más memoria y mantiene un solo proceso. Con 1 worker, una generación de
# documento (10-60 s) dejaba al servidor sin atender ningún otro request.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
