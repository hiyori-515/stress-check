import { NextResponse } from "next/server";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ session_id: string }> }
) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  const { session_id } = await params;
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("ai_hypothesis")
    .select(
      "session_id, summary, category_trends, hypotheses, interview_questions, first_steps, generated_at"
    )
    .eq("session_id", session_id)
    .maybeSingle();

  if (error) {
    console.error("hypothesis fetch failed:", error);
    return NextResponse.json(
      { error: "レポートの取得に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ hypothesis: data });
}
