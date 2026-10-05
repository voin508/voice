# CPU (по умолчанию). GPU: см. README — образ с CUDA и ./install.sh cuda
FROM python:3.12-bookworm

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

ENV DOCKER=1
RUN chmod +x install.sh run.sh \
    && ./install.sh cpu

# Кэш весов — постоянный volume (см. run-docker.sh / run-docker.ps1)
VOLUME /app/.cache

ENTRYPOINT ["./run.sh"]
