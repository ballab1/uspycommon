FROM s2.ubuntu.home:5000/docker.io/python:3.9.21-alpine3.20

RUN pip3 install --upgrade pip && \
    pip3 install --trusted-host 10.152.183.135:3141 drp-package-uspycommon==0.0.4 -i http://10.152.183.135:3141/testuser/simple && \
    rm -r /root/.cache

WORKDIR /app
RUN mkdir -p /app/config

COPY ./main.py /app

ENTRYPOINT ["python", "-u", "main.py"]
