FROM python:3.11-alpine as builder
LABEL maintainer="bruce.schultz@uk-koeln.de"

# Have poetry create .venv/ folder in WORKDIR
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /app

RUN pip install poetry==1.7.1

COPY ./poetry.lock ./pyproject.toml ./

RUN poetry install --no-root --without dev

FROM python:3.11-alpine

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY ./logging.json .
COPY ./gateway/ ./gateway/

# API server port
EXPOSE 5000

ENTRYPOINT ["python", "-m", "gateway.cli", "serve"]

HEALTHCHECK CMD curl --fail http://localhost:5000/health || exit 1
