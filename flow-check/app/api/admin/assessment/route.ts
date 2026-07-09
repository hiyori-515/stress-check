import { NextResponse } from "next/server";
import { CATEGORIES, type Category } from "@/lib/questions";
import {
  createAdminClient,
  getAuthenticatedUser,
} from "@/lib/supabase-admin";

export async function POST(request: Request) {
  const user = await getAuthenticatedUser(request);
  if (!user) {
    return NextResponse.json({ error: "認証が必要です" }, { status: 401 });
  }

  let body: {
    session_id?: string;
    internal_structure_notes?: string;
    confirmed_flow_areas?: unknown;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "リクエストボディが不正です" },
      { status: 400 }
    );
  }

  if (!body.session_id || typeof body.session_id !== "string") {
    return NextResponse.json(
      { error: "session_idが必要です" },
      { status: 400 }
    );
  }
  const areas = Array.isArray(body.confirmed_flow_areas)
    ? body.confirmed_flow_areas
    : [];
  if (!areas.every((a) => CATEGORIES.includes(a as Category))) {
    return NextResponse.json(
      { error: "該当尺度の値が不正です" },
      { status: 400 }
    );
  }

  const supabase = createAdminClient();
  // session_idはUNIQUE。既存があれば上書き（編集可能）
  const { data, error } = await supabase
    .from("final_assessment")
    .upsert(
      {
        session_id: body.session_id,
        internal_structure_notes: body.internal_structure_notes ?? "",
        confirmed_flow_areas: areas,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "session_id" }
    )
    .select(
      "id, session_id, internal_structure_notes, confirmed_flow_areas, updated_at"
    )
    .single();

  if (error || !data) {
    console.error("final_assessment upsert failed:", error);
    return NextResponse.json(
      { error: "最終見立ての保存に失敗しました" },
      { status: 500 }
    );
  }

  return NextResponse.json({ assessment: data });
}
