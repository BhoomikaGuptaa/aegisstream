FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ /app/shared/
COPY services/api/ /app/services/api/
COPY services/evaluator/ /app/services/evaluator/
COPY services/producer/ /app/services/producer/
COPY scripts/ /app/scripts/
ENV PYTHONPATH=/app
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
