FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GOOGLE_CLOUD_PROJECT=aecom-demo-uc1 \
    GOOGLE_CLOUD_LOCATION=global \
    CLOUD_RUN_REGION=us-central1 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

WORKDIR /app

RUN groupadd --gid 10001 appuser && \
    useradd --uid 10001 --gid 10001 --create-home --shell /sbin/nologin appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ask_gbs_agent ./ask_gbs_agent
COPY main.py pyproject.toml README.md ./

RUN mkdir -p /app/ask_gbs_agent/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
