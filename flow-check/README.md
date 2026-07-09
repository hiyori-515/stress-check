# Flow Check

経営者向け診断フォーム＋管理画面（フェーズ1＋フェーズ2）。

- 診断フォーム（認証なし）: 属性入力 → 25問回答 → 完了
- 回答データのSupabase保存とカテゴリ別スコアの自動集計
- 管理画面（Supabase Auth・Email/Passwordログイン）:
  - 回答一覧・個別回答詳細（詳細ビュー / 要点ビューのタブ切り替え）
  - AI仮説レポート生成（Anthropic API・claude-sonnet-4-6）
  - 面談メモの入力・保存（複数件）
  - 最終見立ての入力・保存（内部構造メモ＋該当尺度）
  - ステータス変更（未面談 / 面談済み / レポート送付済み / 伴走移行 / クローズ）

## 技術スタック

- Next.js (App Router) + TypeScript + Tailwind CSS
- Next.js Route Handlers（API）
- Supabase (PostgreSQL / Auth)
- Anthropic API（AI仮説レポート生成）

## セットアップ

### 1. 環境変数

`.env.local` をプロジェクト直下に作成:

```
NEXT_PUBLIC_SUPABASE_URL=<SupabaseプロジェクトURL>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon (publishable) キー>
SUPABASE_SERVICE_ROLE_KEY=<service role (secret) キー>
ANTHROPIC_API_KEY=<Anthropic APIキー。未設定の間は仮説レポート生成時に画面へエラーが表示されます>
```

Vercelにデプロイする場合は、同じ4つを Environment Variables にも設定してください。

### 2. 依存パッケージ

```bash
npm install
```

### 3. DBテーブル作成

SupabaseダッシュボードのSQLエディタで以下を順に実行してください:

1. `supabase/schema.sql`（フェーズ1: respondents / diagnostic_sessions / answers / category_scores）
2. `supabase/schema-phase2.sql`（フェーズ2: ai_hypothesis / interview_notes / final_assessment）

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
    └── admin/                      # 管理API（Bearerトークン認証）
        ├── responses/route.ts              # 回答一覧
        ├── responses/[id]/route.ts         # 回答詳細
        ├── responses/[id]/status/route.ts  # ステータス変更 (PATCH)
        ├── hypothesis/generate/route.ts    # AI仮説レポート生成 (POST)
        ├── hypothesis/[session_id]/route.ts # AI仮説レポート取得 (GET)
        ├── notes/route.ts                  # 面談メモ保存 (POST)
        ├── notes/[session_id]/route.ts     # 面談メモ取得 (GET)
        ├── assessment/route.ts             # 最終見立て保存 (POST)
        └── assessment/[session_id]/route.ts # 最終見立て取得 (GET)
lib/
├── supabase.ts                     # ブラウザ用Supabaseクライアント
├── supabase-admin.ts               # サーバー用（service role）＋認証検証
├── profile.ts                      # 回答者情報の型
├── questions.ts                    # 質問データ定義（25問・5カテゴリ）
├── scoring.ts                      # スコアリングロジック
├── status.ts                       # ステータス選択肢
└── hypothesis.ts                   # AI仮説レポートのプロンプト組み立て・応答解析
components/
├── QuestionCard.tsx
├── ProgressBar.tsx
├── CategoryScoreBar.tsx
├── InterviewNotesSection.tsx       # 面談メモ入力・一覧
└── FinalAssessmentSection.tsx      # 最終見立て入力
supabase/
├── schema.sql                      # フェーズ1スキーマ＋RLSポリシー
└── schema-phase2.sql               # フェーズ2スキーマ（AI仮説・面談メモ・最終見立て）
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
