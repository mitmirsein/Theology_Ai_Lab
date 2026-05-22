# Theology AI Lab - Antigravity 사용자 가이드

> 대상: Antigravity 또는 VS Code 사용자

## 설치

```bash
cd ~/Desktop
git clone https://github.com/mitmirsein/Theology_Ai_Lab.git
cd Theology_Ai_Lab

# uv가 없다면 먼저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 로컬 앱 의존성 설치
uv venv 03_System/venv --python 3.11
source 03_System/venv/bin/activate
uv pip install -e ./03_System
```

## 실행

```bash
source 03_System/venv/bin/activate
cd 03_System
streamlit run app.py
```

## 로컬 인덱싱

1. `01_Library/inbox`에 PDF/EPUB/TXT 파일을 넣습니다.
2. 앱의 **Inbox** 탭에서 메타데이터를 보정합니다.
3. **로컬 인덱싱 시작**을 누릅니다.

## Antigravity 팁

- "Inbox 파일 목록 보여줘"
- "이 PDF에 맞는 sidecar JSON 만들어줘"
- "로컬 인덱싱 로그에서 실패 원인 분석해줘"

Kerygma Press AI Lab
