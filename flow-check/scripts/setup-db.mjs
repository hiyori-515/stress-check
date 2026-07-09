/**
 * DBセットアップ確認スクリプト
 *
 * supabase/schema.sql をSupabaseダッシュボードのSQLエディタで実行したあと、
 * テーブルが正しく作成されているかを確認します。
 *
 * 使い方:
 *   node scripts/setup-db.mjs
 *
 * .env.local の NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY を使用します。
 */
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function loadEnvLocal() {
  const envPath = resolve(import.meta.dirname, "../.env.local");
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match && !process.env[match[1]]) process.env[match[1]] = match[2];
  }
}

loadEnvLocal();

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !serviceRoleKey) {
  console.error(
    ".env.local に NEXT_PUBLIC_SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を設定してください"
  );
  process.exit(1);
}

const supabase = createClient(url, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const TABLES = [
  "respondents",
  "diagnostic_sessions",
  "answers",
  "category_scores",
  // フェーズ2 (schema-phase2.sql)
  "ai_hypothesis",
  "interview_notes",
  "final_assessment",
];

let allOk = true;
for (const table of TABLES) {
  const { error } = await supabase.from(table).select("id").limit(1);
  if (error) {
    allOk = false;
    console.error(`✗ ${table}: ${error.message}`);
  } else {
    console.log(`✓ ${table}: OK`);
  }
}

if (!allOk) {
  console.error(
    "\nテーブルが見つかりません。supabase/schema.sql をSupabaseダッシュボードのSQLエディタで実行してください。"
  );
  process.exit(1);
}
console.log("\nすべてのテーブルが確認できました。");
