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
    .from("interview_notes")
    .select("id, session_id, note_text, interview_date, created_at")
    .eq("session_id", session_id)
    .order("created_at", { ascending: false });

  if (error) {
    console.error("interview_notes fetch failed:", error);
    return NextResponse.json(
      { error: "メモの取得に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ notes: data });
}
