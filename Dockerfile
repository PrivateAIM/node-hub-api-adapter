FROM python:3.13-alpine AS builder
LABEL maintainer="bruce.schultz@uk-koeln.de"

WORKDIR /app

RUN apk add gcc musl-dev libffi-dev git
RUN pip install uv

COPY ./uv.lock ./pyproject.toml ./README.md ./
COPY hub_adapter/ ./hub_adapter/

RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
RUN uv sync --frozen --no-dev

FROM python:3.13-alpine

RUN adduser -u 10000 -D hubadapter

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY hub_adapter/ ./hub_adapter/

RUN chown -R hubadapter:hubadapter /app

EXPOSE 5000

USER 10000:10000

ENTRYPOINT ["hub-adapter", "serve"]
