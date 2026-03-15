FROM python:3.12-slim

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Setup timezone
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo "Asia/Seoul" > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV TZ=Asia/Seoul

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /home/chzzk-data-analytics

COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev

COPY . .
