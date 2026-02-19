FROM python:3.13-alpine AS builder
LABEL maintainer="bruce.schultz@uk-koeln.de"

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /app

RUN apk add gcc musl-dev libffi-dev
RUN pip install poetry==2.2.1

COPY ./poetry.lock ./pyproject.toml ./README.md ./
COPY hub_adapter/ ./hub_adapter/

RUN poetry install --without dev

FROM python:3.13-alpine

RUN adduser -u 10000 -D hubadapter

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY hub_adapter/ ./hub_adapter/

RUN chown -R hubadapter:hubadapter /app

EXPOSE 5000

USER 10000:10000

ENTRYPOINT ["python", "-m", "hub_adapter.cli", "serve"]