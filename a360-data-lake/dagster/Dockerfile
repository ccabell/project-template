FROM python:3.12-slim

WORKDIR /opt/dagster/app

RUN apt-get update && apt-get install -y \
    git curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv (prebuilt binary)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock ./

# Create venv and install deps
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv sync --all-extras && \
    uv cache clean

ENV PATH="/opt/dagster/app/.venv/bin:$PATH"

COPY . .

EXPOSE 4000

CMD ["python", "-m", "dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-f", "repository.py"]
