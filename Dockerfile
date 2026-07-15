# Optional containerised backend. Build context is the project root.
FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data/Incident_Investigation_dataset.xlsx ./data/Incident_Investigation_dataset.xlsx

EXPOSE 8003
# Config (LLM_MODEL, ANTHROPIC_API_KEY, ...) is passed in at run time via env.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
