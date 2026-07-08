"use strict";

/**
 * gas/setup_trigger.gs の Node ベース簡易テスト
 *
 * GAS のグローバルサービス（PropertiesService / SpreadsheetApp / Logger 等）を
 * モックした vm コンテキストで setup_trigger.gs を評価し、
 * _buildApiPayload() と _recordHighStress() の挙動を検証する。
 *
 * 実行方法: node --test gas/tests/
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  readGasSource,
  createMockSheet,
  createMockSpreadsheet,
  loadGas: loadGasSource,
} = require("./helpers");

const GAS_SOURCE = readGasSource("setup_trigger.gs");
const EXPORTS = ["onFormSubmit", "_buildApiPayload", "_recordHighStress"];

function loadGas(overrides = {}) {
  return loadGasSource(GAS_SOURCE, EXPORTS, overrides);
}

// ── _buildApiPayload ──────────────────────────────────────────────

test("_buildApiPayload: namedValues 形式（スプレッドシートバインド）", () => {
  const gas = loadGas({ scriptProperties: { COMPANY_CODE: "ACME" } });

  const payload = gas._buildApiPayload({
    namedValues: {
      "お名前": ["テスト 太郎"],
      "メールアドレス": ["taro@example.com"],
      "所属部署": ["開発部"],
      "性別": ["男性"],
      "年齢区分": ["30〜39歳"],
      "雇用形態": ["正社員"],
      "Q1": ["3"],
      "Q57": ["4"],
      "タイムスタンプ": ["2026/07/07 10:00:00"], // 無関係な列は無視される
    },
  });

  assert.equal(payload.name, "テスト 太郎");
  assert.equal(payload.email, "taro@example.com");
  assert.equal(payload.department, "開発部");
  assert.equal(payload.gender, "男性");
  assert.equal(payload.age_group, "30〜39歳");
  assert.equal(payload.employment_type, "正社員");
  assert.deepEqual(payload.answers, { Q1: 3, Q57: 4 });
  assert.equal(payload.company_code, "ACME");
  assert.equal(payload.version, "57");
  assert.match(payload.response_id, /^GAS-\d+$/);
  assert.ok(!Number.isNaN(Date.parse(payload.submitted_at)));
});

test("_buildApiPayload: e.response 形式（フォーム直接バインド）", () => {
  const gas = loadGas();

  const items = [
    { title: "お名前", value: "花子" },
    { title: "Q2", value: "1" },
    { title: "問3", value: "2" }, // "問" プレフィックスも質問として扱う
  ].map((it) => ({
    getItem: () => ({ getTitle: () => it.title }),
    getResponse: () => it.value,
  }));

  const payload = gas._buildApiPayload({
    response: { getItemResponses: () => items },
  });

  assert.equal(payload.name, "花子");
  assert.deepEqual(payload.answers, { Q2: 1, Q3: 2 });
});

test("_buildApiPayload: メタ情報が無い場合は空文字、COMPANY_CODE 未設定は UNKNOWN", () => {
  const gas = loadGas();

  const payload = gas._buildApiPayload({ namedValues: { "Q1": ["2"] } });

  assert.equal(payload.name, "");
  assert.equal(payload.email, "");
  assert.equal(payload.department, "");
  assert.equal(payload.company_code, "UNKNOWN");
  assert.deepEqual(payload.answers, { Q1: 2 });
});

test("_buildApiPayload: 質問タイトルの前後空白は無視される", () => {
  const gas = loadGas();

  const payload = gas._buildApiPayload({
    namedValues: { " お名前 ": ["太郎"], " Q5 ": ["4"] },
  });

  assert.equal(payload.name, "太郎");
  assert.deepEqual(payload.answers, { Q5: 4 });
});

// ── _recordHighStress ─────────────────────────────────────────────

const PAYLOAD = {
  response_id: "GAS-1751900000000",
  name: "テスト 太郎",
  email: "taro@example.com",
  department: "開発部",
};

test("_recordHighStress: HIGH_STRESS_SHEET_ID のシートにヘッダー + 1行追記される", () => {
  const ss = createMockSpreadsheet();
  const openedIds = [];
  const gas = loadGas({
    scriptProperties: { HIGH_STRESS_SHEET_ID: "sheet-123" },
    SpreadsheetApp: {
      openById(id) { openedIds.push(id); return ss; },
      getActiveSpreadsheet() { throw new Error("openById を使うべき"); },
    },
  });

  gas._recordHighStress(PAYLOAD, { high_stress: true, high_stress_reason: "㋐" });

  assert.deepEqual(openedIds, ["sheet-123"]);
  const sheet = ss.sheets["高ストレス者"];
  assert.ok(sheet, "「高ストレス者」シートが作成される");
  assert.equal(sheet.rows.length, 2);
  assert.deepEqual(sheet.rows[0], [
    "記録日時", "response_id", "氏名", "メールアドレス", "所属部署", "判定理由",
  ]);
  const row = sheet.rows[1];
  assert.equal(typeof row[0].getTime, "function", "1列目は Date");
  assert.deepEqual(row.slice(1), [
    "GAS-1751900000000", "テスト 太郎", "taro@example.com", "開発部", "㋐",
  ]);
});

test("_recordHighStress: 既存シートにはヘッダーを重複追加しない", () => {
  const existing = createMockSheet([
    ["記録日時", "response_id", "氏名", "メールアドレス", "所属部署", "判定理由"],
    [new Date(), "GAS-1", "既存", "a@example.com", "総務部", "㋑"],
  ]);
  const ss = createMockSpreadsheet({ "高ストレス者": existing });
  const gas = loadGas({
    scriptProperties: { HIGH_STRESS_SHEET_ID: "sheet-123" },
    SpreadsheetApp: { openById: () => ss },
  });

  gas._recordHighStress(PAYLOAD, { high_stress: true, high_stress_reason: "㋑" });

  assert.equal(existing.rows.length, 3, "データ行のみ1行追加される");
  assert.equal(existing.rows[2][1], "GAS-1751900000000");
});

test("_recordHighStress: SHEET_ID 未設定時はバインド先スプレッドシートへ記録する", () => {
  const ss = createMockSpreadsheet();
  const gas = loadGas({
    SpreadsheetApp: {
      openById() { throw new Error("SHEET_ID 未設定なので呼ばれないはず"); },
      getActiveSpreadsheet: () => ss,
    },
  });

  gas._recordHighStress(PAYLOAD, { high_stress: true, high_stress_reason: "㋐" });

  assert.equal(ss.sheets["高ストレス者"].rows.length, 2);
});

test("_recordHighStress: 記録先が無い場合は HIGH_STRESS_SHEET_ID を促すエラー", () => {
  const gas = loadGas(); // openById なし・getActiveSpreadsheet は null

  assert.throws(
    () => gas._recordHighStress(PAYLOAD, { high_stress: true }),
    /HIGH_STRESS_SHEET_ID/
  );
});

test("_recordHighStress: high_stress_reason が無い場合は空文字で記録する", () => {
  const ss = createMockSpreadsheet();
  const gas = loadGas({
    scriptProperties: { HIGH_STRESS_SHEET_ID: "sheet-123" },
    SpreadsheetApp: { openById: () => ss },
  });

  gas._recordHighStress(PAYLOAD, { high_stress: true, high_stress_reason: null });

  assert.equal(ss.sheets["高ストレス者"].rows[1][5], "");
});
