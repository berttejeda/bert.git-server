FROM python:2.7-alpine as base
FROM base as builder

RUN apk add --no-cache git make musl-dev gcc

RUN mkdir -p /app/lib
RUN mkdir -p /app/repos

WORKDIR /app

ADD config.ini .
ADD requirements.txt .
ADD git-server.py .

RUN pip install -t /app/lib -r /app/requirements.txt

FROM base

RUN pip install gunicorn

# copy from builder
COPY --from=builder /app /app

WORKDIR /app

ENTRYPOINT [ "/app/git-server.py" ]
CMD []