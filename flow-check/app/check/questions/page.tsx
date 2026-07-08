"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import ProgressBar from "@/components/ProgressBar";
import QuestionCard from "@/components/QuestionCard";
import { PROFILE_STORAGE_KEY, type Profile } from "@/lib/profile";
import { QUESTIONS, TOTAL_QUESTIONS } from "@/lib/questions";

const emptySubscribe = () => () => {};

export default function QuestionsPage() {
  const router = useRouter();
  // SSR時はnull、クライアントでsessionStorageから読み込む
  const storedProfile = useSyncExternalStore(
    emptySubscribe,
    () => sessionStorage.getItem(PROFILE_STORAGE_KEY),
    () => null
  );
  const profile = useMemo<Profile | null>(() => {
    if (!storedProfile) return null;
    try {
      return JSON.parse(storedProfile) as Profile;
    } catch {
      return null;
    }
  }, [storedProfile]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    // 属性入力を経ずに直接アクセスされた場合は属性入力へ戻す
    if (!sessionStorage.getItem(PROFILE_STORAGE_KEY)) {
      router.replace("/check/profile");
    }
  }, [router]);

  if (!profile) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p className="text-gray-500">読み込み中...</p>
      </main>
    );
  }

  const question = QUESTIONS[currentIndex];
  const selected = answers[question.no];
  const isLast = currentIndex === TOTAL_QUESTIONS - 1;

  const handleSelect = (value: number) => {
    setAnswers((prev) => ({ ...prev, [question.no]: value }));
  };

  const handleBack = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    } else {
      router.push("/check/profile");
    }
  };

  const handleNext = async () => {
    if (selected === undefined) return;
    if (!isLast) {
      setCurrentIndex(currentIndex + 1);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await fetch("/api/check/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile,
          answers: QUESTIONS.map((q) => ({
            question_no: q.no,
            score: answers[q.no],
          })),
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error ?? "送信に失敗しました");
      }
      sessionStorage.removeItem(PROFILE_STORAGE_KEY);
      router.push("/check/complete");
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : "送信に失敗しました。時間をおいて再度お試しください。"
      );
      setSubmitting(false);
    }
  };

  return (
    <main className="flex-1 px-4 py-10 bg-gray-50">
      <div className="max-w-xl mx-auto">
        <div className="mb-8">
          <ProgressBar current={currentIndex + 1} total={TOTAL_QUESTIONS} />
        </div>
        <QuestionCard
          question={question}
          selected={selected}
          onSelect={handleSelect}
        />
        {submitError && (
          <p className="mt-4 text-sm text-red-500 text-center">
            {submitError}
          </p>
        )}
        <div className="flex gap-4 mt-8">
          <button
            type="button"
            onClick={handleBack}
            disabled={submitting}
            className="flex-1 border border-gray-300 text-gray-700 font-medium py-3 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
          >
            戻る
          </button>
          <button
            type="button"
            onClick={handleNext}
            disabled={selected === undefined || submitting}
            className="flex-1 bg-navy hover:bg-navy-dark text-white font-bold py-3 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "送信中..." : isLast ? "回答を送信する" : "次へ"}
          </button>
        </div>
      </div>
    </main>
  );
}
