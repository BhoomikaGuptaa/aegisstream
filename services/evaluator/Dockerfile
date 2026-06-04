FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ /app/shared/
COPY services/ /app/services/
ENV PYTHONPATH=/app
CMD ["python", "services/evaluator/app/main.py"]
