FROM python:3.9-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Ensure the .streamlit directory is created and secrets.toml is copied
# RUN mkdir -p /app/.streamlit
# COPY .streamlit/secrets.toml /app/.streamlit/secrets.toml

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]