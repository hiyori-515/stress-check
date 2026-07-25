# Flow Check

経営者向け診断フォーム＋管理画面（フェーズ1〜3）。

- 診断フォーム（認証なし）: 属性入力 → 25問回答 → 完了（レーダーチャートで結果を表示）
- 回答データのSupabase保存とカテゴリ別スコアの自動集計
- 管理画面（Supabase Auth・Email/Passwordログイン）:
  - 回答一覧・個別回答詳細（詳細ビュー / 要点ビューのタブ切り替え。要点ビューはレーダーチャート表示）
  - AI仮説レポート生成（Anthropic API・claude-sonnet-4-6）
  - 面談メモの入力・保存（複数件）
  - 最終見立ての入力・保存（内部構造メモ＋経営者向けコメント＋該当尺度）
  - ステータス変更（未面談 / 面談済み / レポート送付済み / 伴走移行 / クローズ）
  - 経営者向けPDFレポートの生成・プレビュー・ダウンロード（4ページ構成）

## 技術スタック

- Next.js (App Router) + TypeScript + Tailwind CSS
- Next.js Route Handlers（API）
- Supabase (PostgreSQL / Auth)
- Anthropic API（AI仮説レポート生成）
- @react-pdf/renderer（PDFレポート生成・Noto Sans JP同梱: `assets/fonts/`）

## セットアップ

### 1. 環境変数

`.env.local` をプロジェクト直下に作成:

```
NEXT_PUBLIC_SUPABASE_URL=<SupabaseプロジェクトURL>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon (publishable) キー>
SUPABASE_SERVICE_ROLE_KEY=<service role (secret) キー>
ANTHROPIC_API_KEY=<Anthropic APIキー。未設定の間は仮説レポート生成時に画面へエラーが表示されます>

# 任意: 新規回答のChatwork通知。未設定なら通知をスキップする
CHATWORK_API_TOKEN=<Chatwork APIトークン>
CHATWORK_ROOM_ID=<通知先のルームID>
# 任意: 通知内の管理画面URLのベース（独自ドメインに移行した場合に指定）
NEXT_PUBLIC_SITE_URL=https://flow-check-eta.vercel.app
```

Vercelにデプロイする場合は、同じものを Environment Variables にも設定してください
（Supabaseの3つは必須。Anthropic・Chatworkは該当機能を使う場合のみ）。

### 2. 依存パッケージ

```bash
npm install
```

### 3. DBテーブル作成

SupabaseダッシュボードのSQLエディタで以下を順に実行してください:

1. `supabase/schema.sql`（フェーズ1: respondents / diagnostic_sessions / answers / category_scores）
2. `supabase/schema-phase2.sql`（フェーズ2: ai_hypothesis / interview_notes / final_assessment）
3. `supabase/schema-phase3.sql`（フェーズ3: final_assessmentにclient_facing_commentを追加）

実行後、以下でテーブルが作成されたか確認できます:

```bash
node scripts/setup-db.mjs
```

### 4. 管理者アカウント作成（初回のみ）

```bash
node scripts/create-admin.mjs <メールアドレス> <パスワード>
```

### 5. 開発サーバー起動

```bash
npm run dev
```

- 診断フォーム: http://localhost:3000/
- 管理画面: http://localhost:3000/admin/login

## ディレクトリ構成

```
app/
├── page.tsx                        # 導入ページ
├── check/
│   ├── profile/page.tsx            # 属性入力
│   ├── questions/page.tsx          # 診断本体（25問）
│   └── complete/page.tsx           # 回答完了
├── admin/
│   ├── login/page.tsx              # 管理ログイン
│   ├── responses/page.tsx          # 回答一覧
│   └── responses/[id]/page.tsx     # 個別回答詳細
└── api/
    ├── check/submit/route.ts       # 回答送信API（認証不要）
    ├── check/scores/[session_id]/route.ts # 完了画面のスコア取得（認証不要・スコアのみ返す）
    ├── health/db/route.ts          # 接続診断
    ├── cron/keep-alive/route.ts    # Supabase自動停止防止（Vercel Cron・要CRON_SECRET）
    └── admin/                      # 管理API（Bearerトークン認証）
        ├── responses/route.ts              # 回答一覧
        ├── responses/[id]/route.ts         # 回答詳細
        ├── responses/[id]/status/route.ts  # ステータス変更 (PATCH)
        ├── hypothesis/generate/route.ts    # AI仮説レポート生成 (POST)
        ├── hypothesis/[session_id]/route.ts # AI仮説レポート取得 (GET)
        ├── notes/route.ts                  # 面談メモ保存 (POST)
        ├── notes/[session_id]/route.ts     # 面談メモ取得 (GET)
        ├── assessment/route.ts             # 最終見立て保存 (POST)
        ├── assessment/[session_id]/route.ts # 最終見立て取得 (GET)
        └── report/[session_id]/route.ts    # PDFレポート生成 (GET, application/pdf)
lib/
├── supabase.ts                     # ブラウザ用Supabaseクライアント
├── supabase-admin.ts               # サーバー用（service role）＋認証検証
├── profile.ts                      # 回答者情報の型
├── questions.ts                    # 質問データ定義（25問・5カテゴリ）
├── scoring.ts                      # スコアリングロジック
├── status.ts                       # ステータス選択肢
├── hypothesis.ts                   # AI仮説レポートのプロンプト組み立て・応答解析
└── chatwork.ts                     # 新規回答のChatwork通知（メッセージ組み立て＋送信）
components/
├── QuestionCard.tsx
├── ProgressBar.tsx
├── CategoryScoreBar.tsx            # 横棒グラフ（詳細ビュー用）
├── RadarScoreChart.tsx             # レーダーチャート（recharts）。variantで管理用/回答者用を切替
├── InterviewNotesSection.tsx       # 面談メモ入力・一覧
├── FinalAssessmentSection.tsx      # 最終見立て入力（経営者向けコメント含む）
└── ReportDocument.tsx              # PDFレポートのレイアウト定義（サーバー専用）
assets/fonts/                       # PDF用 Noto Sans JP（Regular / Bold）
supabase/
├── schema.sql                      # フェーズ1スキーマ＋RLSポリシー
├── schema-phase2.sql               # フェーズ2スキーマ（AI仮説・面談メモ・最終見立て）
└── schema-phase3.sql               # フェーズ3スキーマ（経営者向けコメント）
vercel.json                         # Vercel Cron定義（keep-alive）
scripts/
├── setup-db.mjs                    # テーブル作成確認
└── create-admin.mjs                # 管理者アカウント作成
```

## スコアリング

- 5カテゴリ × 各5問、回答値は0〜4（カテゴリ合計 0〜20）
- レベル判定: 低（0〜7） / 中（8〜13） / 高（14〜20）
- 尺度名の表記: 判断 Decision / 実行 Action / 本音 Voice / 役割 Role / 委譲 Handoff

## AI仮説レポート

- 個別回答詳細（詳細ビュー）の「仮説レポートを生成」ボタンで生成
- Anthropic API（`claude-sonnet-4-6`）を使用し、結果は `ai_hypothesis` に保存（再生成で上書き）
- `ANTHROPIC_API_KEY` が未設定の場合は画面にエラーメッセージを表示

## PDFレポート（経営者向け）

- 個別回答詳細ページ下部の「PDFレポートを生成」ボタンで生成し、画面内でプレビュー・ダウンロードできる
- 4ページ構成: 表紙 / 今回の整理結果（レーダーチャート＋高スコア領域の説明） / 面談で見えてきたこと / 次のステップ
- 3ページ目には最終見立ての「経営者向けコメント」がそのまま掲載される。
  未入力の間は生成ボタンが無効（APIも400を返す）
- 内部構造用語・分析語はPDFに一切出力しない
- フォントはリポジトリ同梱の Noto Sans JP を使用（`next.config.ts` の
  `outputFileTracingIncludes` でVercelのサーバーレス関数にも同梱される）

## トラブルシューティング（回答の保存に失敗する場合）

診断の最後で「回答の保存に失敗しました」と表示される場合、まず本番URLの
`/api/health/db` をブラウザで開いてください。環境変数の設定有無と、各テーブルへの
到達可否・書き込み可否がJSONで表示されます（値そのものは表示されません）。

よくある原因と対処:

| 表示されるコード | 原因 | 対処 |
|---|---|---|
| `unreachable` | Supabaseプロジェクトが一時停止（無料プランは一定期間未使用で自動停止） | Supabaseダッシュボードで Restore / Resume する |
| `42P01` | テーブルが未作成（SQL未実行） | SQLエディタで `supabase/schema.sql` →`schema-phase2.sql` →`schema-phase3.sql` を実行 |
| `42501` | RLSで書き込みが拒否された（anonキーを service role 欄に設定している等） | Vercelの `SUPABASE_SERVICE_ROLE_KEY` に secret（service role）キーを設定して再デプロイ |
| `env_missing` | 環境変数が未設定 | Vercelの Environment Variables を設定して再デプロイ |

保存に失敗しても回答内容は画面に残るため、原因を解消したあと「回答を送信する」を
押し直せばそのまま送信できます。

> 補足: 回答保存では、挿入したIDをアプリ側で採番しています。これは
> `insert().select()` がRLSの**読み取り**ポリシー（認証済みのみ）にも依存してしまい、
> キー設定を誤ると保存できなくなるためです。

## 完了画面のレーダーチャート

- 回答送信後、`session_id` をsessionStorageで完了画面に引き継ぎ、
  `GET /api/check/scores/[session_id]` で5尺度のスコアを取得して表示する
- 表示するのは数値の可視化のみ。解釈・診断的コメント・高スコアの強調は行わない
  （解釈は面談で伝えるため）。`RadarScoreChart` の `variant="respondent"` がこれにあたる
- スコアが取得できない場合・5尺度が揃わない場合はチャートを出さず、
  テキストのみの画面を表示する（回答者にエラーは見せない）
- スコア取得APIは認証不要だが、返すのはスコアのみ。氏名・会社名・メール・
  個別回答は返さない。`session_id` はUUIDのため推測できない

## Supabaseの自動停止（pause）防止

Supabase無料プランは約1週間アクセスがないとプロジェクトを自動停止します。
これを防ぐため、Vercel Cronで1日1回 `GET /api/cron/keep-alive` を呼び、
接続実績を作っています。

- スケジュール: `vercel.json` の `crons` で毎日 UTC 03:00（日本時間 12:00）
- 認証: Vercel Cronが付与する `Authorization: Bearer <CRON_SECRET>` を検証。
  一致しない場合と `CRON_SECRET` 未設定の場合は401（fail close）
- `CRON_SECRET` はcron定義時にVercelが自動生成するため、手動設定は不要
- 応答は `{ ok, count, timestamp }` のみ。テーブル構成や環境変数の状態は返さない
  （診断情報が必要な場合は `/api/health/db` を使う）
- Hobbyプランではcronは1日1回が上限。7日間の猶予に対して十分

デプロイ後、Vercelダッシュボードの Settings → Cron Jobs で登録を確認できます。
同画面の Run から手動実行も可能です。

## 新規回答のChatwork通知

回答が保存されたあと、Chatworkへ通知を送ります（`lib/chatwork.ts`）。

- 送信タイミング: `POST /api/check/submit` で保存・採点がすべて成功した直後
- 通知内容: 会社名・氏名・役職・業種・従業員数・きっかけ・回答日時(JST)・管理画面リンク。
  **メールアドレスと電話番号は含めない**
- `CHATWORK_API_TOKEN` / `CHATWORK_ROOM_ID` が未設定なら通知をスキップする（fail open）
- 通知の失敗・タイムアウト（3秒）は握りつぶし、回答者には正常完了を返す。
  失敗の内容はサーバーログにのみ出力する
- 管理画面リンクのドメインは `NEXT_PUBLIC_SITE_URL` で上書きできる
  （未設定時は本番URLを使用）
