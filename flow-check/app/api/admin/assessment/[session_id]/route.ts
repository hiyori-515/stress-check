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
    .from("final_assessment")
    .select(
      "id, session_id, internal_structure_notes, client_facing_comment, confirmed_flow_areas, updated_at"
    )
    .eq("session_id", session_id)
    .maybeSingle();

  if (error) {
    console.error("final_assessment fetch failed:", error);
    return NextResponse.json(
      { error: "最終見立ての取得に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ assessment: data });
}
