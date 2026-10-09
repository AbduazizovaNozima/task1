FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml ./
COPY bot ./bot
RUN pip install --no-cache-dir ".[bot]"

USER nobody
CMD ["python", "-m", "bot.main"]
