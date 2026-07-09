/** 診断セッションのステータス選択肢 */
export const STATUS_OPTIONS = [
  "未面談",
  "面談済み",
  "レポート送付済み",
  "伴走移行",
  "クローズ",
] as const;

export type SessionStatus = (typeof STATUS_OPTIONS)[number];
