FROM python:3.10

ENV PYTHONUNBUFFERED=1
# 增加超时时间和使用国内镜像
ENV UV_HTTP_TIMEOUT=300
# ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
# ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
# ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn


ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app/

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
# COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
COPY --from=ghcr.nju.edu.cn/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

COPY pyproject.toml ./
RUN uv lock --index-url https://mirrors.aliyun.com/pypi/simple/


# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
#RUN --mount=type=cache,target=/root/.cache/uv \
#    --mount=type=bind,source=uv.lock,target=uv.lock \
#    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
#    uv sync --frozen --no-install-project

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml

ENV PYTHONPATH=/app

COPY ./scripts /app/scripts

COPY ./pyproject.toml ./uv.lock ./alembic.ini /app/

COPY ./app /app/app

# 复制静态文件
COPY ./static /app/static

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

CMD ["fastapi", "run", "--workers", "4", "app/main.py"]
