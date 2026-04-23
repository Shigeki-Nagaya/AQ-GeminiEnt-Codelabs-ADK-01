# Changelog

## [v2.0] - 2026-04-23

### Added
- `personal_assistant/agent.py`: `before_agent_callback` によるSlack通知機能
  - ユーザー入力をCloud Function経由でSlack Incoming Webhookに転送
  - 通知内容: タイムスタンプ(JST)、セッションID、ユーザー入力テキスト
  - 通知失敗時は `logger.warning` に記録し、エージェント処理は継続
- `personal_assistant/.env`: `CLOUD_FUNCTION_URL` エントリを追加

## [v1.0] - 2026-04-23

### Added
- `personal_assistant/agent.py`: `gemini-2.5-flash` を使った `root_agent` の初期実装
- `personal_assistant/.env`: Vertex AI 接続設定
- `.gitignore`: `.venv/`, `.env`, `.adk/`, `__pycache__/` 等を除外
- `deploy.py`: Vertex AI Agent Engine へのデプロイスクリプト
- `README.md`: セットアップ・実行・デプロイ手順

### Deployed
- Agent Engine: `projects/813649126279/locations/asia-northeast1/reasoningEngines/734816814982234112`
