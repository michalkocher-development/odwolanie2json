# odwolanie2json – obraz aplikacji (CLI + interfejs web). Bez GPU: modele wywoływane przez API (config/settings.yaml).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/ config/
COPY web/ web/
RUN mkdir -p input output trace

EXPOSE 8000
# domyślnie interfejs web; tryb wsadowy: docker compose run --rm cli
CMD ["python", "-m", "app.web", "--host", "0.0.0.0", "--port", "8000"]
