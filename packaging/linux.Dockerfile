# Linux release builds: Ubuntu 22.04 keeps the binary compatible with glibc 2.35 and newer, like the CI runner.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get install -y --no-install-recommends python3.13 python3.13-venv python3.13-tk libpython3.13 binutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3.13 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt "pyinstaller>=6.0" \
    && chmod -R a+rwX /opt/venv

ENV PYTHON=python3.13 VENV=/opt/venv
