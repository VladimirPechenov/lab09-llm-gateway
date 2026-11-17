FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY gateway ./gateway
RUN pip install --no-cache-dir .
RUN useradd --create-home npc
USER npc
EXPOSE 8000
CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
