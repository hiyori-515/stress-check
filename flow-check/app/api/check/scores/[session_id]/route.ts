import { NextResponse } from "next/server";
import { CATEGORIES } from "@/lib/questions";
import { createAdminClient } from "@/lib/supabase-admin";

/**
 * 完了画面のレーダーチャート用にカテゴリ別スコアを返す（認証不要）。
 *
 * 回答者本人が直後に自分の結果を見るための入口。session_idはUUIDで推測不能、
 * かつ返すのはスコアのみ（氏名・会社名・メール・個別回答は返さない）。
 */
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ session_id: string }> }
) {
  const { session_id } = await params;
  if (!UUID_PATTERN.test(session_id)) {
    return NextResponse.json({ error: "見つかりません" }, { status: 404 });
  }

  let supabase;
  try {
    supabase = createAdminClient();
  } catch (error) {
    console.error("supabase client init failed:", error);
    return NextResponse.json(
      { error: "スコアの取得に失敗しました" },
      { status: 500 }
    );
  }

  const { data, error } = await supabase
    .from("category_scores")
    .select("category, total_score, level")
    .eq("session_id", session_id);

  if (error) {
    console.error("category_scores fetch failed:", error);
    return NextResponse.json(
      { error: "スコアの取得に失敗しました" },
      { status: 500 }
    );
  }

  // 5尺度すべてが揃っている場合のみ返す（欠けている場合はチャートを出さない）
  const isComplete =
    !!data &&
    CATEGORIES.every((category) =>
      data.some((row) => row.category === category)
    );
  if (!isComplete) {
    return NextResponse.json({ error: "見つかりません" }, { status: 404 });
  }

  return NextResponse.json({ scores: data });
}
