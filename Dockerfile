# Use an official Ubuntu as a base image
FROM ubuntu:22.04
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Setup timezone
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo "Asia/Seoul" > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata
ENV TZ=Asia/Seoul

# Install system dependencies
RUN apt-get -y --no-install-recommends install \
    build-essential curl libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev wget xz-utils coreutils \
    libxml2-dev libffi-dev liblzma-dev git ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pyenv and Python
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
RUN curl https://pyenv.run | bash \
    && eval "$(pyenv init --path)" \
    && eval "$(pyenv init -)" \
    && pyenv install 3.12.8 && pyenv global 3.12.8

# Install poetry
ENV PATH="/root/.local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set working directory and permissions
RUN mkdir -p /home/chzzk-data-analytics
WORKDIR /home/chzzk-data-analytics
COPY . /home/chzzk-data-analytics

# Install custom dependencies
RUN apt-get update \
    && apt-get -y --no-install-recommends install \
    tmux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*