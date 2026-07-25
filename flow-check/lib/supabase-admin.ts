import { createClient, type User } from "@supabase/supabase-js";

/** 必須の環境変数を取得する。未設定なら理由が分かる形で失敗させる */
function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `環境変数 ${name} が設定されていません（Vercelの Environment Variables を確認してください）`
    );
  }
  return value;
}

/**
 * サーバー専用: service roleキーを使うSupabaseクライアント。
 * Route Handler以外（クライアントコンポーネント等）からimportしないこと。
 */
export function createAdminClient() {
  return createClient(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("SUPABASE_SERVICE_ROLE_KEY"),
    { auth: { persistSession: false, autoRefreshToken: false } }
  );
}

/**
 * Authorization: Bearer <access_token> を検証し、認証済みユーザーを返す。
 * 未認証・無効トークンの場合はnull。
 */
export async function getAuthenticatedUser(
  request: Request
): Promise<User | null> {
  const authHeader = request.headers.get("authorization");
  if (!authHeader?.toLowerCase().startsWith("bearer ")) return null;
  const token = authHeader.slice(7).trim();
  if (!token) return null;

  const supabase = createClient(
    requireEnv("NEXT_PUBLIC_SUPABASE_URL"),
    requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    { auth: { persistSession: false, autoRefreshToken: false } }
  );
  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) return null;
  return data.user;
}

/** Supabaseのエラーから、対処が分かる日本語のヒントを組み立てる */
export function describeSupabaseError(error: {
  code?: string;
  message?: string;
} | null): { code: string; hint: string } {
  const code = error?.code || "unknown";
  const message = error?.message ?? "";

  // Supabaseに到達できない（プロジェクトの一時停止、URL誤り、ネットワーク断）
  if (/fetch failed|ENOTFOUND|ECONNREFUSED|network|timeout/i.test(message)) {
    return {
      code: "unreachable",
      hint: "Supabaseに接続できません。Supabaseダッシュボードでプロジェクトが一時停止(Paused)していないか、NEXT_PUBLIC_SUPABASE_URL が正しいかを確認してください。",
    };
  }
  // テーブル未作成（SQL未実行）
  if (code === "42P01" || /does not exist/i.test(message)) {
    return {
      code,
      hint: "テーブルが存在しません。SupabaseのSQLエディタで supabase/schema.sql を実行してください。",
    };
  }
  // RLSで拒否（service roleキーではなくanonキーが設定されている場合など）
  if (code === "42501" || /row-level security|permission denied/i.test(message)) {
    return {
      code,
      hint: "書き込みが拒否されました。Vercelの SUPABASE_SERVICE_ROLE_KEY に service role（secret）キーが設定されているか確認してください。",
    };
  }
  // 認証エラー（キーが誤り）
  if (/JWT|api key|Invalid authentication/i.test(message)) {
    return {
      code,
      hint: "Supabaseの認証に失敗しました。SUPABASE_SERVICE_ROLE_KEY の値を確認してください。",
    };
  }
  return { code, hint: message || "原因不明のエラーです。" };
}
