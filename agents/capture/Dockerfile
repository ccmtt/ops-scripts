FROM python:3.11-slim

WORKDIR /agent

RUN apt-get update \
    && apt-get install -y --no-install-recommends tcpdump tshark \
    && rm -rf /var/lib/apt/lists/*

COPY agents/capture/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY agents/capture/app/main.py ./app/main.py

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
