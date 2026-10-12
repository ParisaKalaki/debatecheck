
FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir streamlit uvicorn

ENV PYTHONPATH=/app/backend
ENV DEBATECHECK_API_URL=http://127.0.0.1:8002
ENV PYTHONUNBUFFERED=1

EXPOSE 8501

CMD ["python", "start.py"]

