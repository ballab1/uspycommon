 docker container rm test &>/dev/null
 docker run --name test --mount type=bind,source="$(pwd)"/config,target=/app/config s2.ubuntu.home:5000/alpine/simple_job:v1 "0" "8"
