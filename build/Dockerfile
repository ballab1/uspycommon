ARG FROM_BASE="${FROM_BASE:-${DOCKER_REGISTRY}docker.io/python:3.13.2-alpine3.21}"
FROM $FROM_BASE

RUN apk update \
    && apk add git jq libffi-dev gcc musl-dev librdkafka-dev

WORKDIR /usr/src
COPY requirements.txt .

RUN set -x \
   && python -m venv ./venv \
   && source ./venv/bin/activate \
   && python -m pip install --no-cache-dir -r requirements.txt \
   && pip install build twine \
   && rm -r /root/.cache \
   && adduser -h /app -s sh -g 100 -D -H -u 1026 builder \
   && export PATH=$PATH:/app

USER builder
WORKDIR /app

CMD [ 'python' ]