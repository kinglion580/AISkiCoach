#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python app/initial_data.py

# Initialize TimescaleDB configuration
python app/init_timescale.py

# 生产环境优化：压缩、保留策略、连续聚合
python app/optimize_timescale.py
