# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.9.12 as builder
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update -y

RUN apt install -y git

RUN mkdir -p /app/repos /etc/git-server


WORKDIR /setup

ADD . .

RUN pip install .

WORKDIR /app

ADD etc/config.yaml /etc/git-server/config.yaml

RUN rm -rf /setup

ENTRYPOINT [ "bt.git-server" ]
CMD ["-f", "/etc/git-server/config.yaml"]