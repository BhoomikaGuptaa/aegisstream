FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/dashboard/ /app/services/dashboard/
ENV PYTHONPATH=/app
CMD ["streamlit", "run", "services/dashboard/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
