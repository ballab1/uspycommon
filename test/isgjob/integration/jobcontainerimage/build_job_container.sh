#!/usr/bin/env bash
set -e
set -o pipefail

declare -r TOP="$(realpath $(dirname ${BASH_SOURCE[0]}))"
# declare -r PARENT="$(dirname $TOP)"
declare -r DOCKER_IMAGE=s2.ubuntu.home:5000/alpine/simple_job:v1

rm -rf "$TOP"/tmp-docker-build/
mkdir -p "$TOP"/tmp-docker-build
cp "${TOP}"/main.py "$TOP"/tmp-docker-build/
cp ./Dockerfile "$TOP"/tmp-docker-build/

# docker build --no-cache --tag $DOCKER_IMAGE "$TOP"/tmp-docker-build
docker build --tag $DOCKER_IMAGE "$TOP"/tmp-docker-build

docker push $DOCKER_IMAGE

cat <<EOF

##############################################################################################
Pushed 'docker push $DOCKER_IMAGE' to push to DOCKER REGISTRY.
##############################################################################################

EOF
