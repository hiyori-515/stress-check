export type Category =
  | "judgment"
  | "execution"
  | "honesty"
  | "roles"
  | "delegation";

export interface Question {
  no: number;
  category: Category;
  text: string;
}

export const CATEGORIES: Category[] = [
  "judgment",
  "execution",
  "honesty",
  "roles",
  "delegation",
];

export const CATEGORY_LABELS: Record<Category, string> = {
  judgment: "判断の流れ",
  execution: "実行の流れ",
  honesty: "本音の流れ",
  roles: "役割の流れ",
  delegation: "委譲の流れ",
};

export const SCALE_OPTIONS = [
  { value: 0, label: "まったく当てはまらない" },
  { value: 1, label: "あまり当てはまらない" },
  { value: 2, label: "どちらともいえない" },
  { value: 3, label: "やや当てはまる" },
  { value: 4, label: "よく当てはまる" },
] as const;

export const QUESTIONS: Question[] = [
  // カテゴリA: judgment
  {
    no: 1,
    category: "judgment",
    text: "ふと振り返ると、今日も自分が一番多く「それでいこう」と言っていた",
  },
  {
    no: 2,
    category: "judgment",
    text: "「これ、どうしましょう」と聞かれて、自分が答えるのが当たり前になっている",
  },
  {
    no: 3,
    category: "judgment",
    text: "自分がいなかったとき、判断が保留されて待たれていたことがある",
  },
  {
    no: 4,
    category: "judgment",
    text: "自分が決めなくてもよさそうなことでも、確認が回ってくる",
  },
  {
    no: 5,
    category: "judgment",
    text: "誰かが決めたことでも、自分が「いいよ」と言わないと動き出さない空気がある",
  },
  // カテゴリB: execution
  {
    no: 6,
    category: "execution",
    text: "会議で決まったはずのことを、翌週もう一度確認している自分がいる",
  },
  {
    no: 7,
    category: "execution",
    text: "「やります」という返事のあと、次に進捗を聞くのはいつも自分からになる",
  },
  {
    no: 8,
    category: "execution",
    text: "一度決めたやり方が、気づくと前のやり方に戻っている",
  },
  {
    no: 9,
    category: "execution",
    text: "新しいことを始めようとしたとき、現場の空気が少し重くなるのを感じる",
  },
  {
    no: 10,
    category: "execution",
    text: "こちらから確認しないと、途中経過が上がってこないことがある",
  },
  // カテゴリC: honesty
  {
    no: 11,
    category: "honesty",
    text: "会議が静かに終わったあと、別の場所で話が動いていることがある",
  },
  {
    no: 12,
    category: "honesty",
    text: "「聞いていないですか？」と、自分だけ知らない話が出てくることがある",
  },
  {
    no: 13,
    category: "honesty",
    text: "状況を聞いたとき、具体的な中身よりも「大丈夫です」が先に返ってくる",
  },
  {
    no: 14,
    category: "honesty",
    text: "誰かの不満を、本人からではなく別の人から聞くことがある",
  },
  {
    no: 15,
    category: "honesty",
    text: "意見を言った人が、その後あまり発言しなくなった場面を見たことがある",
  },
  // カテゴリD: roles
  {
    no: 16,
    category: "roles",
    text: "何か問題が起きたとき、「誰が対応するか」がその場で決まることが多い",
  },
  {
    no: 17,
    category: "roles",
    text: "同じ注意や同じ確認を、自分が何度も繰り返している気がする",
  },
  {
    no: 18,
    category: "roles",
    text: "自分と現場の間に立って動いてくれる人が少ないと感じる",
  },
  {
    no: 19,
    category: "roles",
    text: "同じ業務でも、やる人がそのときどきで変わることがある",
  },
  {
    no: 20,
    category: "roles",
    text: "「これは誰の担当だっけ」と、あとから整理し直すことがある",
  },
  // カテゴリE: delegation
  {
    no: 21,
    category: "delegation",
    text: "任せたつもりでも、途中で気になって確認してしまうことがある",
  },
  {
    no: 22,
    category: "delegation",
    text: "任せた仕事について、相手がどう判断したのかが見えにくいことがある",
  },
  {
    no: 23,
    category: "delegation",
    text: "自分が関わらなかった場面で、あとから想定外の結果になっていたことがある",
  },
  {
    no: 24,
    category: "delegation",
    text: "任せた相手から「どこまでやっていいですか」と聞かれることがある",
  },
  {
    no: 25,
    category: "delegation",
    text: "経験を積んでほしい場面ほど、つい自分が先に対応してしまう",
  },
];

export const TOTAL_QUESTIONS = QUESTIONS.length;

export const INDUSTRY_OPTIONS = [
  "医療・福祉",
  "建設・不動産",
  "製造",
  "IT・通信",
  "小売・飲食",
  "士業・コンサル",
  "教育",
  "その他",
] as const;

export const EMPLOYEE_COUNT_OPTIONS = [
  "1〜5名",
  "6〜10名",
  "11〜30名",
  "31〜50名",
  "51〜100名",
  "101名以上",
] as const;

export const LEAD_SOURCE_OPTIONS = [
  "BNI",
  "SNS(X)",
  "SNS(LinkedIn)",
  "SNS(Facebook)",
  "紹介",
  "その他",
] as const;
