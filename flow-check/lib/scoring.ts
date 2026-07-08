import { CATEGORIES, type Category } from "./questions";

export type Level = "低" | "中" | "高";

export interface AnswerInput {
  question_no: number;
  score: number;
}

export interface CategoryScore {
  category: Category;
  total_score: number;
  level: Level;
}

/** 質問番号からカテゴリを判定する（1〜5: judgment, 6〜10: execution, ...） */
export function categoryForQuestion(questionNo: number): Category {
  if (questionNo < 1 || questionNo > 25 || !Number.isInteger(questionNo)) {
    throw new Error(`質問番号が不正です: ${questionNo}`);
  }
  return CATEGORIES[Math.floor((questionNo - 1) / 5)];
}

/** 合計スコア（0〜20）からレベルを判定する */
export function levelForScore(totalScore: number): Level {
  if (totalScore <= 7) return "低";
  if (totalScore <= 13) return "中";
  return "高";
}

/** 25問の回答からカテゴリ別スコアを集計する */
export function computeCategoryScores(answers: AnswerInput[]): CategoryScore[] {
  const totals: Record<Category, number> = {
    judgment: 0,
    execution: 0,
    honesty: 0,
    roles: 0,
    delegation: 0,
  };
  for (const answer of answers) {
    totals[categoryForQuestion(answer.question_no)] += answer.score;
  }
  return CATEGORIES.map((category) => ({
    category,
    total_score: totals[category],
    level: levelForScore(totals[category]),
  }));
}
