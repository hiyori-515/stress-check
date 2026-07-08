/**
 * 管理者アカウント作成スクリプト（初期セットアップ時に1回だけ実行）
 *
 * 使い方:
 *   node scripts/create-admin.mjs <メールアドレス> <パスワード>
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

const [email, password] = process.argv.slice(2);
if (!email || !password) {
  console.error("使い方: node scripts/create-admin.mjs <メールアドレス> <パスワード>");
  process.exit(1);
}

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

const { data, error } = await supabase.auth.admin.createUser({
  email,
  password,
  email_confirm: true,
});

if (error) {
  console.error(`管理者アカウントの作成に失敗しました: ${error.message}`);
  process.exit(1);
}

console.log(`管理者アカウントを作成しました: ${data.user.email}`);
console.log("/admin/login からログインできます。");
