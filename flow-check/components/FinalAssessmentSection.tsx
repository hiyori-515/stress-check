"use client";

import { useEffect, useState } from "react";
import { CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/questions";

interface FinalAssessmentSectionProps {
  sessionId: string;
  token: string;
}

export default function FinalAssessmentSection({
  sessionId,
  token,
}: FinalAssessmentSectionProps) {
  const [notes, setNotes] = useState("");
  const [areas, setAreas] = useState<Category[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await fetch(`/api/admin/assessment/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const body = await response.json();
        if (body.assessment) {
          setNotes(body.assessment.internal_structure_notes ?? "");
          setAreas(
            Array.isArray(body.assessment.confirmed_flow_areas)
              ? body.assessment.confirmed_flow_areas
              : []
          );
          setUpdatedAt(body.assessment.updated_at ?? null);
        }
      } else {
        setError("最終見立ての取得に失敗しました");
      }
      setLoaded(true);
    };
    load();
  }, [sessionId, token]);

  const toggleArea = (category: Category) => {
    setAreas((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
    setMessage(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    const response = await fetch("/api/admin/assessment", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
        internal_structure_notes: notes,
        confirmed_flow_areas: areas,
      }),
    });
    setSaving(false);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setError(body?.error ?? "最終見立ての保存に失敗しました");
      return;
    }
    const body = await response.json();
    setUpdatedAt(body.assessment.updated_at ?? null);
    setMessage("保存しました");
  };

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-navy">最終見立て</h2>
        {updatedAt && (
          <span className="text-xs text-gray-500">
            最終更新:{" "}
            {new Date(updatedAt).toLocaleString("ja-JP", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>
      {!loaded ? (
        <p className="text-sm text-gray-500">読み込み中...</p>
      ) : (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label
              htmlFor="internal_structure_notes"
              className="block text-sm font-medium mb-1"
            >
              内部構造メモ
            </label>
            <p className="text-xs text-gray-500 mb-2">
              ※このメモは管理画面専用です。内部構造用語を使って構いません。
            </p>
            <textarea
              id="internal_structure_notes"
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                setMessage(null);
              }}
              rows={6}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-navy"
            />
          </div>
          <fieldset>
            <legend className="block text-sm font-medium mb-2">
              該当する尺度（複数選択可）
            </legend>
            <div className="flex flex-wrap gap-3">
              {CATEGORIES.map((category) => (
                <label
                  key={category}
                  className={`flex items-center gap-2 border rounded-lg px-3 py-2 cursor-pointer text-sm ${
                    areas.includes(category)
                      ? "border-navy bg-navy-light text-navy font-medium"
                      : "border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={areas.includes(category)}
                    onChange={() => toggleArea(category)}
                    className="accent-[#1a365d]"
                  />
                  {CATEGORY_LABELS[category]}
                </label>
              ))}
            </div>
          </fieldset>
          {error && <p className="text-sm text-red-500">{error}</p>}
          {message && <p className="text-sm text-green-600">{message}</p>}
          <button
            type="submit"
            disabled={saving}
            className="bg-navy hover:bg-navy-dark text-white font-bold px-6 py-2 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </form>
      )}
    </section>
  );
}
