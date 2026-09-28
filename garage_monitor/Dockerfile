FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV GARAGE_DATA_DIR=/data TZ=Europe/Rome
VOLUME ["/data"]
CMD ["python", "-m", "garage_agent", "run"]
