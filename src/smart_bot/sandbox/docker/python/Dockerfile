FROM python:3.12-slim

# 安装编译工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    cmake \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /sandbox/workspace
WORKDIR /sandbox/workspace

CMD ["sleep", "infinity"]