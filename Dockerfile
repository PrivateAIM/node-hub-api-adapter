FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder
ENV UV_COMPILE_BYTECODE=1
LABEL maintainer="bruce.schultz@uk-koeln.de"

# Configure the Python directory so it is consistent
ENV UV_PYTHON_INSTALL_DIR=/python

# Only use the managed Python version
ENV UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app

#RUN apk add gcc musl-dev libffi-dev git
RUN apk add git

COPY ./uv.lock ./pyproject.toml ./

RUN uv sync --frozen --no-install-project --no-dev
ADD . /app
RUN uv sync --frozen --no-dev

FROM python:3.12-alpine

RUN adduser -u 10000 hubadapter -D

COPY --from=builder --chown=hubadapter:hubadapter /app/.venv /app/.venv
COPY --chown=hubadapter:hubadapter hub_adapter/ ./hub_adapter/

ENV PATH="/app/.venv/bin:$PATH"


# API server port
EXPOSE 5000

USER 10000:10000

ENTRYPOINT ["python", "-m", "hub_adapter.cli", "serve"]
