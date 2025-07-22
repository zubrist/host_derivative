FROM python:3.8

WORKDIR /app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWEITEBYTECODE 1
ENV PYTHONPATH /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

