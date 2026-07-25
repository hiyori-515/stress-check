"use client";

import { useEffect, useState } from "react";
import RadarScoreChart from "@/components/RadarScoreChart";
import { RESULT_SESSION_STORAGE_KEY } from "@/lib/profile";
import type { Category } from "@/lib/questions";
import type { Level } from "@/lib/scoring";

interface CategoryScore {
  category: Category;
  total_score: number;
  level: Level;
}

export default function CompletePage() {
  const [scores, setScores] = useState<CategoryScore[] | null>(null);

  useEffect(() => {
    const load = async () => {
      const sessionId = sessionStorage.getItem(RESULT_SESSION_STORAGE_KEY);
      if (!sessionId) return;
      try {
        const response = await fetch(`/api/check/scores/${sessionId}`);
        if (!response.ok) return;
        const body = await response.json();
        if (Array.isArray(body.scores) && body.scores.length === 5) {
          setScores(body.scores);
        }
      } catch {
        // 取得に失敗してもチャートを出さないだけ。回答者にエラーは見せない
      }
    };
    load();
  }, []);

  return (
    <main className="flex-1 flex items-center justify-center px-4 py-12">
      <div className="max-w-xl w-full text-center">
        <h1 className="text-3xl font-bold text-navy mb-8">
          ご回答ありがとうございます。
        </h1>

        {scores && (
          <section className="mb-10">
            <h2 className="text-lg font-bold text-navy mb-1">
              あなたの組織の流れ
            </h2>
            <div className="mx-auto w-full max-w-[400px]">
              <RadarScoreChart
                scores={scores}
                variant="respondent"
                height={300}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              低 0〜7 ／ 中 8〜13 ／ 高 14〜20
            </p>
          </section>
        )}

        <p className="text-gray-700 leading-relaxed">
          回答内容をもとに、面談前の整理を行います。
          <br />
          担当者より、面談のご案内をお送りいたします。
        </p>
      </div>
    </main>
  );
}
