import { NextResponse } from "next/server";
import { createAdminClient } from "@/lib/supabase-admin";

/**
 * Supabaseの自動停止(pause)を防ぐためのkeep-alive。
 * Vercel Cronから1日1回呼ばれ、軽量なクエリでDBへの接続実績を作る。
 *
 * 診断情報は返さない（テーブル構成や環境変数の状態は /api/health/db 側の責務）。
 */
export async function GET(request: Request) {
  // Vercel Cronは Authorization: Bearer <CRON_SECRET> を付けてくる。
  // CRON_SECRET未設定時に "Bearer undefined" が通ってしまわないよう、
  // 未設定なら常に拒否する（fail close）。
  const cronSecret = process.env.CRON_SECRET;
  const authHeader = request.headers.get("authorization");
  if (!cronSecret || authHeader !== `Bearer ${cronSecret}`) {
    if (!cronSecret) {
      console.error("keep-alive: CRON_SECRET が未設定のため拒否しました");
    }
    return NextResponse.json(
      { ok: false, error: "Unauthorized" },
      { status: 401 }
    );
  }

  try {
    const supabase = createAdminClient();
    // 行データは転送せず件数のみ取得する（最も軽い問い合わせ）
    const { count, error } = await supabase
      .from("respondents")
      .select("id", { count: "exact", head: true });

    if (error) {
      console.error("keep-alive query failed:", error);
      return NextResponse.json(
        { ok: false, error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      ok: true,
      count: count ?? 0,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("keep-alive failed:", error);
    return NextResponse.json(
      {
        ok: false,
        error: error instanceof Error ? error.message : "不明なエラー",
      },
      { status: 500 }
    );
  }
}
