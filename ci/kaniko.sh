
# this file intentionaly has no '#!/bin/sh' because it runs in different environments:
#  '#!/bin/sh'  '#!/busybox/sh'

[ "${DEBUG:-0}" != 0 ] && set -x

KANIKO_IMAGE="${DOCKER_REGISTRY}docker.io/bitnami/kaniko:1.25.0-debian-12-r4"

################################################################################
build() {
    build_cmd $DOCKER
    build_args
    build_params
}

################################################################################
build_args() {
    sed -E -e 's|^([^#=]+)=.*$|\1|' -e '/^(\s*#.*)*$/d' 'ci/.env' | \
    while read -r param; do
        printf '%s %s \n' '--build-arg' "'$param=$(print_arg "$param")'"
    done
}

################################################################################
build_cmd() {
    if [ $1 = 'iskaniko' ]; then
        echo '/kaniko/executor'
    else
        # have to create a copy of DOCKER_SECRET
        # because some local environment permissions prevent access to original file
        cp ~/.docker/config.json $DOCKER_SECRET
        printf '%s \n' 'docker run --rm' \
                       "--volume '$WORKSPACE:$WORKSPACE'" \
                       "--volume '$DOCKER_SECRET:/kaniko/.docker/config.json:ro'" \
                       "--user '0:$GID'" \
                       "'$KANIKO_IMAGE'"
    fi
}

################################################################################
build_params() {
    printf '%s \n' \
       '--cache=false' \
       '--insecure' \
       '--skip-tls-verify' \
       '--verbosity info' \
       "--context 'dir://$WORKSPACE'" \
       "--destination '$TARGET'" \
       '--dockerfile ci/Dockerfile' \
       '--insecure' \
       '--insecure-pull' \
       "--label 'container.build.time=$CONTAINER_BUILD_TIME'" \
       "--label 'container.fingerprint=$CONTAINER_FINGERPRINT'" \
       "--label 'container.git.commit=$CONTAINER_GIT_COMMIT'" \
       "--label 'container.git.refs=$CONTAINER_GIT_REFS'" \
       "--label 'container.git.url=$CONTAINER_GIT_URL'" \
       "--label 'container.origin=$CONTAINER_ORIGIN'" \
       "--label 'container.original.name=$CONTAINER_NAME'" \
       "--label 'container.os=$CONTAINER_OS'" \
       "--label 'container.parent=$FROM_BASE'" \
       "--label 'container.build.host=$CONTAINER_BUILD_HOST'"
}

################################################################################
exit_handler() {
    # ensure we delete any files created
    [ -f $DOCKER_SECRET ] && rm $DOCKER_SECRET
}

################################################################################
is_docker() {
    if [ -e /kaniko/executor ]; then
        echo 'iskaniko'
    else
        echo 'native'
    fi
}

################################################################################
print_arg () {
    arg=$1
    eval argval=\"\$$arg\"
    echo "$argval"
}

################################################################################
#                 MAIN
################################################################################

DOCKER=$(is_docker)

# search for '.env' file and make sure WORKSPACE coresponds to the directory it is in
if [ "${WORKSPACE}" ] && [ -f "${WORKSPACE}/ci/.env" ]; then
    cd "$WORKSPACE" ||:

elif [ -f ci/.env ]; then
    WORKSPACE="$(pwd)"

elif [ "$DOCKER" = 'native' ]; then
    WORKSPACE="$(readlink -f "$(dirname "$0")/..")"
    cd "$WORKSPACE" ||:
fi
# remove any training backslash
WORKSPACE="$(echo $WORKSPACE | sed 's:/*$::')"


# specify Docker secret
if [ $DOCKER = 'native' ]; then
    DOCKER_SECRET=${WORKSPACE}/.secret.json
    trap exit_handler EXIT
fi

if [ ! -f 'ci/.env' ]; then
    echo 'No environment definition file'
    exit 1
fi

. ci/.env

# show pretty version of the command
echo $(build) | sed -E -e 's| --| \\\n   --|g'

# build container using kaniko
eval $(build)
