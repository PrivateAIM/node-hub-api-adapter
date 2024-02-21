FROM python:3.11-alpine as builder
LABEL maintainer="bruce.schultz@uk-koeln.de"

# Have poetry create .venv/ folder in WORKDIR
ENV POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /app

RUN pip install poetry==1.7.1

COPY ./poetry.lock ./pyproject.toml ./

RUN poetry install --no-ansi --without dev

FROM python:3.11-alpine

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY ./gateway/ ./gateway/
RUN pip list

# API server port
EXPOSE 5000

ENTRYPOINT ["python", "gateway/cli.py", "serve"]
