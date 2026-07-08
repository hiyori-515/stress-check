import { createClient, type User } from "@supabase/supabase-js";

/**
 * サーバー専用: service roleキーを使うSupabaseクライアント。
 * Route Handler以外（クライアントコンポーネント等）からimportしないこと。
 */
export function createAdminClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
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
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { auth: { persistSession: false, autoRefreshToken: false } }
  );
  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) return null;
  return data.user;
}
