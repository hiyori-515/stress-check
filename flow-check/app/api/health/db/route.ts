import { NextResponse } from "next/server";
import {
  createAdminClient,
  describeSupabaseError,
} from "@/lib/supabase-admin";

/**
 * 接続診断用エンドポイント。ブラウザで /api/health/db を開くと、
 * 環境変数の設定有無と各テーブルへの到達可否が確認できる。
 * 値そのものは返さない（設定されているかどうかのみ）。
 */
const TABLES = [
  "respondents",
  "diagnostic_sessions",
  "answers",
  "category_scores",
  "ai_hypothesis",
  "interview_notes",
  "final_assessment",
] as const;

export async function GET() {
  const env = {
    NEXT_PUBLIC_SUPABASE_URL: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
    ANTHROPIC_API_KEY: !!process.env.ANTHROPIC_API_KEY,
  };

  if (!env.NEXT_PUBLIC_SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    return NextResponse.json(
      {
        ok: false,
        env,
        hint: "Vercelの Environment Variables に NEXT_PUBLIC_SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を設定し、再デプロイしてください。",
      },
      { status: 500 }
    );
  }

  const supabase = createAdminClient();
  const tables: Record<string, { ok: boolean; code?: string; hint?: string }> =
    {};
  let allOk = true;

  for (const table of TABLES) {
    const { error } = await supabase.from(table).select("id").limit(1);
    if (error) {
      allOk = false;
      tables[table] = { ok: false, ...describeSupabaseError(error) };
    } else {
      tables[table] = { ok: true };
    }
  }

  // 書き込み権限の確認（RLSでINSERTが拒否されていないか）。
  // 検証用の行はすぐ削除するため、データは残らない。
  let writable: { ok: boolean; code?: string; hint?: string } = { ok: true };
  if (tables.respondents?.ok) {
    const probeId = crypto.randomUUID();
    const { error: insertError } = await supabase.from("respondents").insert({
      id: probeId,
      name: "__healthcheck__",
      company_name: "__healthcheck__",
      position: "__healthcheck__",
      industry: "その他",
      employee_count: "1〜5名",
      email: "healthcheck@example.invalid",
      lead_source: "その他",
    });
    if (insertError) {
      allOk = false;
      writable = { ok: false, ...describeSupabaseError(insertError) };
    } else {
      await supabase.from("respondents").delete().eq("id", probeId);
    }
  }

  return NextResponse.json(
    { ok: allOk, env, tables, writable },
    { status: allOk ? 200 : 500 }
  );
}
