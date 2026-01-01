# Theology AI Lab v2 - Docker Image
# =================================
# Docker + uv 기반 표준화 배포 이미지

FROM python:3.11-slim

# 시스템 패키지 설치 (OCR + PDF 처리)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OCR 엔진 및 언어팩
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    tesseract-ocr-grc \
    tesseract-ocr-heb \
    tesseract-ocr-kor \
    # PDF 처리
    poppler-utils \
    # 빌드 도구
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 (빠른 Python 패키지 관리자)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 (Docker 캐싱 최적화)
COPY pyproject.toml ./
# uv.lock이 있으면 복사 (없으면 무시)
COPY uv.loc[k] ./

# 의존성 설치
RUN uv sync --no-dev || uv sync

# 소스 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000
EXPOSE 8501

# 환경 변수 기본값
ENV CHROMA_DB_DIR=/app/vector_db \
    ARCHIVE_DIR=/app/01_Library/archive \
    INBOX_DIR=/app/01_Library/inbox \
    OCR_ENABLED=true \
    LOG_LEVEL=INFO

# 실행 (MCP 서버 + Streamlit GUI)
CMD ["./start.sh"]
