FROM ghcr.io/eclipse-sumo/sumo:v1_27_1@sha256:87623396d3501ca8d0ac25154e202bc38baa55a31c724e4dfd6ae60f297c6bf2

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends iproute2 openssl python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY requirements/network.lock ./requirements/network.lock
COPY src ./src
COPY scripts ./scripts
RUN python3 -m pip install --no-cache-dir -r requirements/network.lock

ENV PYTHONPATH=/workspace/src
ENTRYPOINT []
