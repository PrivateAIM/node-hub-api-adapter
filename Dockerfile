FROM python:3.11-alpine as builder
LABEL maintainer="bruce.schultz@uk-koeln.de"

# Have poetry create .venv/ folder in WORKDIR
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /app

RUN apk add gcc musl-dev libffi-dev
RUN pip install poetry==1.8.4

COPY ./poetry.lock ./pyproject.toml ./

RUN poetry install --no-root --without dev

FROM python:3.11-alpine

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY hub_adapter/ ./hub_adapter/

# API server port
EXPOSE 5000

ENTRYPOINT ["python", "-m", "hub_adapter.cli", "serve"]
