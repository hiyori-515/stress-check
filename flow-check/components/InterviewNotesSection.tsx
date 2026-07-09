"use client";

import { useEffect, useState } from "react";

interface InterviewNote {
  id: string;
  note_text: string;
  interview_date: string | null;
  created_at: string;
}

interface InterviewNotesSectionProps {
  sessionId: string;
  token: string;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function InterviewNotesSection({
  sessionId,
  token,
}: InterviewNotesSectionProps) {
  const [notes, setNotes] = useState<InterviewNote[] | null>(null);
  const [noteText, setNoteText] = useState("");
  const [interviewDate, setInterviewDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const response = await fetch(`/api/admin/notes/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) {
        const body = await response.json();
        setNotes(body.notes);
      } else {
        setError("メモの取得に失敗しました");
      }
    };
    load();
  }, [sessionId, token]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteText.trim()) {
      setError("メモを入力してください");
      return;
    }
    setSaving(true);
    setError(null);
    const response = await fetch("/api/admin/notes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
        note_text: noteText,
        interview_date: interviewDate || null,
      }),
    });
    setSaving(false);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      setError(body?.error ?? "メモの保存に失敗しました");
      return;
    }
    const body = await response.json();
    setNotes((prev) => [body.note, ...(prev ?? [])]);
    setNoteText("");
    setInterviewDate("");
  };

  return (
    <section className="bg-white border border-gray-200 rounded-xl p-6">
      <h2 className="text-lg font-bold text-navy mb-4">面談メモ</h2>
      <form onSubmit={handleSave} className="space-y-3 mb-6">
        <div>
          <label
            htmlFor="interview_date"
            className="block text-sm font-medium mb-1"
          >
            面談日
          </label>
          <input
            id="interview_date"
            type="date"
            value={interviewDate}
            onChange={(e) => setInterviewDate(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-navy"
          />
        </div>
        <div>
          <label htmlFor="note_text" className="block text-sm font-medium mb-1">
            メモ
          </label>
          <textarea
            id="note_text"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={5}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-navy"
            placeholder="面談で聞いたこと、気づいたことを自由に記録"
          />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={saving}
          className="bg-navy hover:bg-navy-dark text-white font-bold px-6 py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? "保存中..." : "保存"}
        </button>
      </form>

      {notes === null ? (
        <p className="text-sm text-gray-500">読み込み中...</p>
      ) : notes.length === 0 ? (
        <p className="text-sm text-gray-500">保存されたメモはありません。</p>
      ) : (
        <ul className="space-y-3">
          {notes.map((note) => (
            <li
              key={note.id}
              className="border border-gray-100 rounded-lg p-4 bg-gray-50"
            >
              <div className="flex justify-between text-xs text-gray-500 mb-2">
                <span>
                  面談日: {note.interview_date ?? "-"}
                </span>
                <span>記録: {formatDateTime(note.created_at)}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{note.note_text}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
