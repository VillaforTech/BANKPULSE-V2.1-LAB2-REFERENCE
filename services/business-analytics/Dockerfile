FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 10002 --system analytics
USER analytics
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8087"]
