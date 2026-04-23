# Cloud Tasks 重複排除問題 調査メモ

## 背景

Gemini Enterprise から Agent Engine を呼び出すと、1回の入力に対して
**2つの独立したリクエスト（異なる invocation_id・session_id）** が発生する。
これは Gemini Enterprise の内部仕様（Hedged Request / 並列冗長化）と推定される。

Slack通知が2回届く問題を解決するため、Cloud Tasks の task name dedupe
（同一 invocation_id → 同一 task name → AlreadyExists で2回目を抑止）を試みた。

---

## 試みた対策と結果

### IAM権限付与（全て失敗）

Agent Engine のコンテナが使用する SA:
`service-813649126279@gcp-sa-aiplatform-re.iam.gserviceaccount.com`

付与したロール（全て効果なし）:
- `roles/cloudtasks.enqueuer`（プロジェクトレベル）
- `roles/cloudtasks.enqueuer`（キューレベル）
- `roles/cloudtasks.taskRunner`（プロジェクトレベル）
- `roles/cloudtasks.admin`（プロジェクトレベル）

エラー:
```
403 The principal (user or service account) lacks IAM permission
"cloudtasks.tasks.create" for the resource
"projects/813649126279/locations/asia-northeast1/queues/slack-notifier-queue"
```

### 確認済み事項

- `roles/cloudtasks.enqueuer` には `cloudtasks.tasks.create` が含まれている（確認済み）
- Cloud Tasks API は有効（確認済み）
- Organization Policy による制限はなし（確認済み）
- `gcp-sa-aiplatform-re` は Google 管理のサービスエージェントであり、
  通常の IAM バインディングが効かない可能性がある

### ローカル（adk web）では成功した理由

`adk web` では `gcloud auth application-default login` のユーザー認証
（`s_nagaya@neural-group.com`）で動作する。
このユーザーは `roles/owner` を持つため Cloud Tasks への書き込みが成功した。

Agent Engine 上では `gcp-sa-aiplatform-re` SA で動作するため、
ローカルでの成功は SA の権限とは無関係。
「ローカルで動いた = SA に権限がある」ではないことに注意。

### 現在の実装

Cloud Tasks を断念し、httpx で Cloud Run を直接呼ぶ方式に戻した。
重複排除なし（2回通知が来ることを許容）。

---

## 次にやるべきこと

### 調査方針A: gcp-sa-aiplatform-re への権限付与方法を調べる

`gcp-sa-aiplatform-re` はサービスエージェントであり、
通常の SA とは異なる権限管理が必要な可能性がある。

確認すべき点:
1. Vertex AI Agent Engine の公式ドキュメントで、
   Agent Engine から外部 GCP サービスを呼ぶ際の推奨 IAM 設定を確認する
2. `roles/aiplatform.reasoningEngineServiceAgent` ロールの定義を確認し、
   Cloud Tasks 関連の権限が含まれているか調べる
3. Google Cloud サポートに問い合わせる

### 調査方針B: Cloud Tasks の代替として Pub/Sub を使う

Pub/Sub は Agent Engine からの呼び出しで動作実績がある可能性がある。
`roles/pubsub.publisher` を同 SA に付与して試す。

### 調査方針C: Cloud Logging アラートに切り替える

callback → structured log → Cloud Logging →
log-based alerting → Slack notification channel

重複ログが2本出ても、alerting policy 側で
`time between notifications` を短く設定することで
実質的に毎回通知に近い動作が可能。
