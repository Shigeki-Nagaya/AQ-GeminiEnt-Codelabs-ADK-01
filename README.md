# AI Agents ADK

GCP Agent Development Kit (ADK) を使ったエージェント開発プロジェクト。

## 構成

```
ai-agents-adk/
├── .gitignore
├── .venv/                  # Python 3.12 仮想環境（uv管理）
├── .vscode/
│   └── launch.json
├── deploy.py               # Agent Engine デプロイスクリプト
└── personal_assistant/
    ├── __init__.py
    ├── .env                # 環境変数（Gitに含めない）
    └── agent.py            # root_agent 定義
```

## セットアップ

### 仮想環境の有効化

```bash
source .venv/bin/activate
```

### 依存パッケージのインストール

```bash
uv pip install google-adk "google-cloud-aiplatform[adk,agent_engines]"
```

### 環境変数

`personal_assistant/.env` に以下を設定：

```
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=<your-project-id>
GOOGLE_CLOUD_LOCATION=asia-northeast1
```

## ローカル実行

日本語入力のため、Web UIを推奨：

```bash
adk web
```

ブラウザで `http://localhost:8000` を開く。

`adk run` を使う場合はロケールを設定：

```bash
export PYTHONIOENCODING=utf-8
export LANG=ja_JP.UTF-8
adk run personal_assistant
```

## Agent Engine へのデプロイ

事前に認証を済ませておく：

```bash
gcloud auth application-default login
```

デプロイ実行：

```bash
python deploy.py
```

### デプロイ済みリソース

| 項目 | 値 |
|------|-----|
| Project | quality-assurance-486505 |
| Location | asia-northeast1 |
| Resource name | `projects/813649126279/locations/asia-northeast1/reasoningEngines/734816814982234112` |

別セッションからの利用：

```python
import vertexai
from vertexai import agent_engines

vertexai.init(project="quality-assurance-486505", location="asia-northeast1")
agent = agent_engines.get("projects/813649126279/locations/asia-northeast1/reasoningEngines/734816814982234112")
```

ログ確認: https://console.cloud.google.com/logs/query?project=quality-assurance-486505

## 注意事項

- `.env` と `.adk/`（ローカルセッションDB）は `.gitignore` で除外済み
- `session.db` の中身確認には VSCode拡張 [SQLite Viewer](https://marketplace.visualstudio.com/items?itemName=qwtel.sqlite-viewer) が便利
