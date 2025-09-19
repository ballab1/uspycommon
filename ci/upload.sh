#!/bin/bash -x

declare -r PROJ_DIR=/home/bobb/GIT/drp-uspycommon
declare -r IMAGE=registry.ubuntu.home/alpine/python/3.13.2:latest
#declare -r IMAGE=registry.ubuntu.home/docker.io/python:3.13.2-alpine3.21
declare -r WORK_DIR=/app


docker run --detach --name python --rm --interactive --tty --volume "$PROJ_DIR:$WORK_DIR" --entrypoint /bin/cat "$IMAGE"
docker exec --tty --workdir "$WORK_DIR" --env TWINE_PASSWORD=123 --env TWINE_USERNAME=testuser --env TWINE_REPOSITORY=devpi python sh -c "\
  source /usr/src/venv/bin/activate &&\
  python -m twine upload --verbose --disable-progress-bar --non-interactive ./dist/* --config-file ci/stg-pypirc
"
docker stop python
exit


docker exec --tty --workdir "$WORK_DIR" --env TWINE_PASSWORD=123 --env TWINE_USER=testuser --env TWINE_REPOSITORY=devpi python sh <<EOF
  source /usr/src/venv/bin/activate
  python -m twine upload --verbose --disable-progress-bar --non-interactive ./dist/* --config-file ci/stg-pypirc
EOF
docker stop python
