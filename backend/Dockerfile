FROM python:3.11-slim
WORKDIR /app
# No TA-Lib C lib for v1 — engine_3 uses pandas indicators (keeps the image small
# and avoids the host/container talib divergence). Re-add if a fast C indicator is needed.
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x start.sh
EXPOSE 8080
CMD ["./start.sh"]
