# Flow Check

経営者向け診断フォーム＋管理画面（フェーズ1）。

- 診断フォーム（認証なし）: 属性入力 → 25問回答 → 完了
- 回答データのSupabase保存とカテゴリ別スコアの自動集計
- 管理画面（Supabase Auth・Email/Passwordログイン）: 回答一覧・個別回答詳細

## 技術スタック

- Next.js (App Router) + TypeScript + Tailwind CSS
- Next.js Route Handlers（API）
- Supabase (PostgreSQL / Auth)

## セットアップ

### 1. 環境変数

`.env.local` をプロジェクト直下に作成:

```
NEXT_PUBLIC_SUPABASE_URL=<SupabaseプロジェクトURL>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon (publishable) キー>
SUPABASE_SERVICE_ROLE_KEY=<service role (secret) キー>
```

### 2. 依存パッケージ

```bash
npm install
```

### 3. DBテーブル作成

SupabaseダッシュボードのSQLエディタで `supabase/schema.sql` の内容を実行してください。
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
    └── admin/responses/            # 管理API（Bearerトークン認証）
        ├── route.ts                # 一覧
        └── [id]/route.ts           # 詳細
lib/
├── supabase.ts                     # ブラウザ用Supabaseクライアント
├── supabase-admin.ts               # サーバー用（service role）＋認証検証
├── profile.ts                      # 回答者情報の型
├── questions.ts                    # 質問データ定義（25問・5カテゴリ）
└── scoring.ts                      # スコアリングロジック
components/
├── QuestionCard.tsx
├── ProgressBar.tsx
└── CategoryScoreBar.tsx
supabase/schema.sql                 # DBスキーマ＋RLSポリシー
scripts/
├── setup-db.mjs                    # テーブル作成確認
└── create-admin.mjs                # 管理者アカウント作成
```

## スコアリング

- 5カテゴリ × 各5問、回答値は0〜4（カテゴリ合計 0〜20）
- レベル判定: 低（0〜7） / 中（8〜13） / 高（14〜20）
