#!/bin/bash
# Theology AI Lab - 서비스 시작 스크립트
# MCP 서버 + Streamlit GUI 동시 실행

echo "Starting Theology AI Lab services..."

# Streamlit GUI 백그라운드 실행
uv run streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &

# MCP 서버 포그라운드 실행
uv run python server.py
