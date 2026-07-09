import { CATEGORIES, CATEGORY_LABELS, QUESTIONS, type Category } from "./questions";
import type { CategoryScore } from "./scoring";

/** AI仮説レポートの5セクション */
export interface HypothesisReport {
  summary: string;
  category_trends: string;
  hypotheses: string[];
  interview_questions: string[];
  first_steps: string[];
}

interface RespondentInfo {
  name: string;
  company_name: string;
  position: string;
  industry: string;
  employee_count: string;
}

interface AnswerRow {
  question_no: number;
  score: number;
}

/** 仮説レポート生成用のプロンプトを組み立てる */
export function buildHypothesisPrompt(
  respondent: RespondentInfo,
  answers: AnswerRow[],
  categoryScores: CategoryScore[]
): string {
  const scoreByCategory = new Map(
    categoryScores.map((s) => [s.category, s])
  );
  const scoreLine = (category: Category) => {
    const s = scoreByCategory.get(category);
    return `- ${CATEGORY_LABELS[category]}: ${s?.total_score ?? 0}/20 (${s?.level ?? "低"})`;
  };

  const answerByNo = new Map(answers.map((a) => [a.question_no, a.score]));
  const answerLines = QUESTIONS.map(
    (q) => `Q${q.no}. ${q.text} → 回答値: ${answerByNo.get(q.no) ?? "-"}/4`
  ).join("\n");

  return `あなたは、臨床心理士・公認心理師である黒川ゆう子氏のFlow Check診断アシスタントです。
以下の診断回答をもとに、面談前の「仮説レポート」を作成してください。

【厳守事項】
- 診断を確定させないこと。すべて「〜の可能性があります」「〜と見える回答です」という仮説の言い方を使うこと。
- 医療的・心理臨床的な診断語（うつ、ストレス、リスク等）を一切使わないこと。
- 結果は「○○型」というラベルではなく、「○○に詰まりが集まっている」という位置の表現で示すこと。
- 5つの尺度名：判断 Decision / 実行 Action / 本音 Voice / 役割 Role / 委譲 Handoff
- 以下の内部構造用語は使ってよいが、経営者向けの文言には絶対に転記しないこと：
  責任の置き場 / 実行導線 / 判断保持力 / 組織力学 / 役割と感情の混線 / 心理的安全性 / メンタルリスク / エンゲージメント
- 「経営MRI」という語は一切使用しないこと。
- 経営者の能力や人格を評価する表現を使わないこと。あくまで「流れ」と「構造」の話として扱うこと。

【入力データ】
回答者: ${respondent.name} / ${respondent.company_name} / ${respondent.position} / ${respondent.industry} / ${respondent.employee_count}

カテゴリ別スコア（スコアが高いほど、その領域に詰まりが集中している）:
${CATEGORIES.map(scoreLine).join("\n")}

各設問の回答:
${answerLines}

【出力形式】
以下の5セクションをJSON形式で出力してください:
{
  "summary": "回答サマリー（高スコア項目を3〜5個、原文に近い言葉で。200字以内）",
  "category_trends": "カテゴリ別傾向（5カテゴリの高中低と簡単な所見。300字以内）",
  "hypotheses": ["仮説1", "仮説2", "仮説3"],
  "interview_questions": ["面談で確認したい問い1", "問い2", "問い3", "問い4", "問い5"],
  "first_steps": ["最初に整えるとよさそうなポイント1", "ポイント2"]
}
日本語で出力。断定的な結論文は書かないこと。`;
}

/**
 * モデルの応答テキストからレポートJSONを取り出す。
 * コードフェンスや前置きが付いていても最初のJSONオブジェクトを抽出する。
 */
export function parseHypothesisResponse(text: string): HypothesisReport {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("応答にJSONが含まれていません");
  }
  const parsed: unknown = JSON.parse(text.slice(start, end + 1));
  if (typeof parsed !== "object" || parsed === null) {
    throw new Error("応答のJSONが不正です");
  }
  const record = parsed as Record<string, unknown>;

  const asText = (key: string): string =>
    typeof record[key] === "string" ? (record[key] as string) : "";
  const asStringArray = (key: string): string[] =>
    Array.isArray(record[key])
      ? (record[key] as unknown[]).filter(
          (item): item is string => typeof item === "string"
        )
      : [];

  const report: HypothesisReport = {
    summary: asText("summary"),
    category_trends: asText("category_trends"),
    hypotheses: asStringArray("hypotheses"),
    interview_questions: asStringArray("interview_questions"),
    first_steps: asStringArray("first_steps"),
  };
  if (!report.summary && report.hypotheses.length === 0) {
    throw new Error("応答のJSONに必要なセクションがありません");
  }
  return report;
}
