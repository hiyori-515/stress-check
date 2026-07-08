"use strict";

/**
 * gas/aggregation.gs の Node ベース簡易テスト
 *
 * aggregation.gs は setup_trigger.gs と別プロジェクトでも動くよう
 * 自己完結している必要があるため、単体で評価する（回帰テストを兼ねる）。
 *
 * 実行方法: node --test gas/tests/
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  readGasSource,
  createMockSheet,
  createMockSpreadsheet,
  loadGas,
} = require("./helpers");

const SOURCE = readGasSource("aggregation.gs");
const EXPORTS = ["runGroupAnalysis", "_aggregateGroups", "_dedupeByKey"];

function load(overrides) {
  return loadGas(SOURCE, EXPORTS, overrides);
}

// ── _aggregateGroups ──────────────────────────────────────────────

test("_aggregateGroups: 部署別の n・高ストレス者数・率を計算する", () => {
  const gas = load();

  const respondents = [
    { department: "開発部", email: "a@example.com" },
    { department: "開発部", email: "b@example.com" },
    { department: "開発部", email: "c@example.com" },
    { department: "開発部", email: "d@example.com" },
    { department: "営業部", email: "e@example.com" },
    { department: "営業部", email: "f@example.com" },
    { department: "営業部", email: "g@example.com" },
  ];
  const highStress = [
    { department: "開発部", email: "a@example.com", response_id: "GAS-1" },
  ];

  const rows = gas._aggregateGroups(respondents, highStress, 3);

  assert.deepEqual(rows, [
    {
      department: "営業部", n: 3, suppressed: false,
      high_stress_count: 0, high_stress_rate: 0,
    },
    {
      department: "開発部", n: 4, suppressed: false,
      high_stress_count: 1, high_stress_rate: 25.0,
    },
  ]);
});

test("_aggregateGroups: 最小人数未満の部署は suppressed で数値が null になる", () => {
  const gas = load();

  const respondents = [
    { department: "小チーム", email: "a@example.com" },
    { department: "小チーム", email: "b@example.com" },
    { department: "大部署", email: "c@example.com" },
    { department: "大部署", email: "d@example.com" },
    { department: "大部署", email: "e@example.com" },
  ];
  const highStress = [
    { department: "小チーム", email: "b@example.com", response_id: "GAS-2" },
  ];

  const rows = gas._aggregateGroups(respondents, highStress, 3);

  const small = rows.find((r) => r.department === "小チーム");
  assert.equal(small.n, 2);
  assert.equal(small.suppressed, true);
  assert.equal(small.high_stress_count, null);
  assert.equal(small.high_stress_rate, null);

  const large = rows.find((r) => r.department === "大部署");
  assert.equal(large.suppressed, false);
  assert.equal(large.high_stress_count, 0);
});

test("_aggregateGroups: 同一メールの重複回答は最新1件のみ数える", () => {
  const gas = load();

  const respondents = [
    { department: "開発部", email: "a@example.com" },
    { department: "総務部", email: "a@example.com" }, // 再回答（後勝ち）
    { department: "総務部", email: "b@example.com" },
  ];
  const highStress = [
    { department: "開発部", email: "a@example.com", response_id: "GAS-1" },
    { department: "総務部", email: "a@example.com", response_id: "GAS-9" }, // 再判定
  ];

  const rows = gas._aggregateGroups(respondents, highStress, 1);

  assert.deepEqual(rows, [
    {
      department: "総務部", n: 2, suppressed: false,
      high_stress_count: 1, high_stress_rate: 50.0,
    },
  ]);
});

test("_aggregateGroups: 高ストレス率は小数第1位に丸められる", () => {
  const gas = load();

  const respondents = [];
  for (let i = 0; i < 3; i++) {
    respondents.push({ department: "A", email: `u${i}@example.com` });
  }
  const highStress = [
    { department: "A", email: "u0@example.com", response_id: "GAS-1" },
  ];

  const rows = gas._aggregateGroups(respondents, highStress, 1);
  assert.equal(rows[0].high_stress_rate, 33.3); // 1/3 = 33.333...%
});

test("_aggregateGroups: 回答も高ストレス記録も空なら空配列", () => {
  const gas = load();
  assert.deepEqual(gas._aggregateGroups([], [], 10), []);
});

// ── _dedupeByKey ──────────────────────────────────────────────────

test("_dedupeByKey: キーが空の記録は重複判定せず残す", () => {
  const gas = load();

  const records = [
    { email: "", department: "A" },
    { email: "", department: "B" },
    { email: "x@example.com", department: "C" },
    { email: "x@example.com", department: "D" },
  ];

  const result = gas._dedupeByKey(records, (r) => r.email);
  assert.equal(result.length, 3);
  assert.equal(result.find((r) => r.email === "x@example.com").department, "D");
});

// ── runGroupAnalysis（結合） ──────────────────────────────────────

const RESPONSES_HEADER = [
  "タイムスタンプ", "お名前", "メールアドレス", "所属部署", "Q1",
];
const HS_HEADER = [
  "記録日時", "response_id", "氏名", "メールアドレス", "所属部署", "判定理由",
];

function respondentRow(email, dept) {
  return ["2026/07/07 10:00:00", "名前", email, dept, "3"];
}

test("runGroupAnalysis: シートを読み込み「集団分析」シートに洗い替え出力する", () => {
  const responsesSheet = createMockSheet([
    RESPONSES_HEADER,
    respondentRow("a@example.com", "開発部"),
    respondentRow("b@example.com", "開発部"),
    respondentRow("c@example.com", "営業部"),
  ]);
  const hsSheet = createMockSheet([
    HS_HEADER,
    [new Date(), "GAS-1", "名前", "a@example.com", "開発部", "㋐"],
  ]);

  const responsesSs = createMockSpreadsheet({ "フォームの回答 1": responsesSheet });
  const hsSs = createMockSpreadsheet({ "高ストレス者": hsSheet });
  const outputSs = createMockSpreadsheet({
    // 前回の集計結果が残っていても洗い替えされることを確認する
    "集団分析": createMockSheet([["古いヘッダー"], ["古いデータ"]]),
  });

  const spreadsheets = {
    "responses-id": responsesSs,
    "hs-id": hsSs,
    "output-id": outputSs,
  };

  const gas = load({
    scriptProperties: {
      RESPONSES_SHEET_ID: "responses-id",
      HIGH_STRESS_SHEET_ID: "hs-id",
      GROUP_ANALYSIS_SHEET_ID: "output-id",
      MIN_GROUP_SIZE: "2",
    },
    SpreadsheetApp: {
      openById: (id) => {
        if (!spreadsheets[id]) throw new Error("unknown id: " + id);
        return spreadsheets[id];
      },
      getActiveSpreadsheet: () => null,
    },
  });

  const result = gas.runGroupAnalysis();

  assert.equal(result.length, 2);

  const out = outputSs.sheets["集団分析"].rows;
  assert.deepEqual(out[0], [
    "部署", "回答者数", "高ストレス者数", "高ストレス率(%)",
    "少人数のため非表示", "集計日時",
  ]);
  assert.equal(out.length, 3, "ヘッダー + 2部署（古いデータは消える）");

  const dev = out.find((r) => r[0] === "開発部");
  assert.equal(dev[1], 2);
  assert.equal(dev[2], 1);
  assert.equal(dev[3], 50.0);
  assert.equal(dev[4], false);

  // 営業部は1名 < MIN_GROUP_SIZE(2) なので非表示
  const sales = out.find((r) => r[0] === "営業部");
  assert.equal(sales[1], 1);
  assert.equal(sales[2], "");
  assert.equal(sales[3], "");
  assert.equal(sales[4], true);
});

test("runGroupAnalysis: 「高ストレス者」シート未作成なら高ストレス0名として集計する", () => {
  const responsesSheet = createMockSheet([
    RESPONSES_HEADER,
    respondentRow("a@example.com", "開発部"),
    respondentRow("b@example.com", "開発部"),
  ]);
  const ss = createMockSpreadsheet({ "フォームの回答 1": responsesSheet });

  const gas = load({
    scriptProperties: { MIN_GROUP_SIZE: "2" },
    SpreadsheetApp: {
      openById: () => { throw new Error("ID未設定なので呼ばれないはず"); },
      getActiveSpreadsheet: () => ss, // バインド先へのフォールバック
    },
  });

  const result = gas.runGroupAnalysis();

  assert.deepEqual(result, [
    {
      department: "開発部", n: 2, suppressed: false,
      high_stress_count: 0, high_stress_rate: 0,
    },
  ]);
  assert.ok(ss.sheets["集団分析"], "出力シートが自動作成される");
});

test("runGroupAnalysis: 回答シートが見つからない場合はシート名を含むエラー", () => {
  const gas = load({
    scriptProperties: { RESPONSES_SHEET_NAME: "存在しないシート" },
    SpreadsheetApp: {
      openById: () => { throw new Error("unexpected"); },
      getActiveSpreadsheet: () => createMockSpreadsheet(),
    },
  });

  assert.throws(() => gas.runGroupAnalysis(), /存在しないシート/);
});
