FROM python@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libatomic1 \
        libexpat1 \
        libgl1 \
        libx11-6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

ENV PYTHONPATH=/workspace/src
ENTRYPOINT []
