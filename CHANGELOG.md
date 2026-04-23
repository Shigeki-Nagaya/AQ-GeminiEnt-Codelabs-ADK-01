# Changelog

## [Unreleased] - 2026-04-23

### Added
- `personal_assistant/agent.py`: `gemini-2.5-flash` を使った `root_agent` の初期実装
- `personal_assistant/.env`: Vertex AI 接続設定
- `.gitignore`: `.venv/`, `.env`, `.adk/`, `__pycache__/` 等を除外
- `deploy.py`: Vertex AI Agent Engine へのデプロイスクリプト
- `README.md`: セットアップ・実行・デプロイ手順

### Deployed
- Agent Engine: `projects/813649126279/locations/asia-northeast1/reasoningEngines/734816814982234112`
