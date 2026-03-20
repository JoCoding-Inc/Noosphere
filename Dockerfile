FROM python:3.11-slim
WORKDIR /app

# typst 설치 (최신 릴리즈 바이너리)
RUN apt-get update && apt-get install -y curl ca-certificates xz-utils && \
    TYPST_VERSION=$(curl -s https://api.github.com/repos/typst/typst/releases/latest | grep '"tag_name"' | cut -d'"' -f4) && \
    curl -L "https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin "typst-x86_64-unknown-linux-musl/typst" && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY backend/ backend/

RUN pip install uv && uv pip install --system -e .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
