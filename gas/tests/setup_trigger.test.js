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
const EXPORTS = [
  "onFormSubmit",
  "_buildApiPayload",
  "_recordHighStress",
  "_sendInterviewGuidance",
];

/** GmailApp.sendEmail の呼び出しを記録するモック */
function createMockGmail() {
  const sent = [];
  return {
    sent,
    sendEmail(to, subject, body, options) {
      sent.push({ to, subject, body, options });
    },
  };
}

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

// ── _sendInterviewGuidance ────────────────────────────────────────

test("_sendInterviewGuidance: 面接指導の案内メールを送信する", () => {
  const gmail = createMockGmail();
  const gas = loadGas({
    scriptProperties: { INTERVIEW_CONTACT: "人事部 健康管理室 kenko@example.com" },
    GmailApp: gmail,
  });

  gas._sendInterviewGuidance(PAYLOAD);

  assert.equal(gmail.sent.length, 1);
  const mail = gmail.sent[0];
  assert.equal(mail.to, "taro@example.com");
  assert.match(mail.subject, /面接指導/);
  assert.equal(mail.options.from, "epiphanypsycho@gmail.com");
  assert.match(mail.body, /テスト 太郎 様/);
  assert.match(mail.body, /労働安全衛生法第66条の10/);
  assert.match(mail.body, /医師による面接指導/);
  assert.match(mail.body, /人事部 健康管理室 kenko@example\.com/);
  assert.match(mail.body, /不利益な取扱い/);
});

test("_sendInterviewGuidance: INTERVIEW_CONTACT 未設定時は返信を窓口として案内する", () => {
  const gmail = createMockGmail();
  const gas = loadGas({ GmailApp: gmail });

  gas._sendInterviewGuidance(PAYLOAD);

  assert.match(gmail.sent[0].body, /本メールへの返信/);
});

test("_sendInterviewGuidance: メールアドレス未入力なら送信しない", () => {
  const gmail = createMockGmail();
  const gas = loadGas({ GmailApp: gmail });

  gas._sendInterviewGuidance({ ...PAYLOAD, email: "" });

  assert.equal(gmail.sent.length, 0);
});

// ── onFormSubmit（結合） ──────────────────────────────────────────

/** API レスポンスを固定で返す UrlFetchApp と PDF 用 Utilities のモック */
function createApiMocks(apiResult) {
  return {
    UrlFetchApp: {
      fetch: () => ({
        getResponseCode: () => 200,
        getContentText: () => JSON.stringify(apiResult),
      }),
    },
    Utilities: {
      base64Decode: (s) => s,
      newBlob: (bytes, type, name) => ({ bytes, type, name }),
    },
  };
}

const FORM_EVENT = {
  namedValues: {
    "お名前": ["テスト 太郎"],
    "メールアドレス": ["taro@example.com"],
    "所属部署": ["開発部"],
    "Q1": ["4"],
  },
};

const EMAIL_PAYLOAD = {
  to: "taro@example.com",
  subject: "ストレスチェック結果",
  body: "結果を添付します",
  pdf_base64: "UERG",
  pdf_filename: "result.pdf",
};

test("onFormSubmit: 高ストレス判定時は結果メールの後に案内メールを別便で送る", () => {
  const gmail = createMockGmail();
  const ss = createMockSpreadsheet();
  const gas = loadGas({
    scriptProperties: { API_URL: "https://api.example.com" },
    GmailApp: gmail,
    SpreadsheetApp: {
      openById: () => { throw new Error("unexpected"); },
      getActiveSpreadsheet: () => ss,
    },
    ...createApiMocks({
      status: "success",
      high_stress: true,
      high_stress_reason: "㋐",
      email_payload: EMAIL_PAYLOAD,
    }),
  });

  gas.onFormSubmit(FORM_EVENT);

  assert.equal(gmail.sent.length, 2, "結果メール + 案内メールの2通");
  assert.equal(gmail.sent[0].subject, "ストレスチェック結果");
  assert.match(gmail.sent[1].subject, /面接指導/);
  assert.equal(gmail.sent[1].to, "taro@example.com");
  assert.equal(ss.sheets["高ストレス者"].rows.length, 2, "高ストレス記録も行われる");
});

test("onFormSubmit: 高ストレスでなければ案内メールは送らない", () => {
  const gmail = createMockGmail();
  const gas = loadGas({
    scriptProperties: { API_URL: "https://api.example.com" },
    GmailApp: gmail,
    ...createApiMocks({
      status: "success",
      high_stress: false,
      email_payload: EMAIL_PAYLOAD,
    }),
  });

  gas.onFormSubmit(FORM_EVENT);

  assert.equal(gmail.sent.length, 1, "結果メールのみ");
  assert.equal(gmail.sent[0].subject, "ストレスチェック結果");
});

test("onFormSubmit: 案内メールの失敗は結果メール送信・高ストレス記録に影響しない", () => {
  const sent = [];
  const gmail = {
    sent,
    sendEmail(to, subject, body, options) {
      if (/面接指導/.test(subject)) throw new Error("送信失敗");
      sent.push({ to, subject, body, options });
    },
  };
  const ss = createMockSpreadsheet();
  const gas = loadGas({
    scriptProperties: { API_URL: "https://api.example.com" },
    GmailApp: gmail,
    SpreadsheetApp: {
      openById: () => { throw new Error("unexpected"); },
      getActiveSpreadsheet: () => ss,
    },
    ...createApiMocks({
      status: "success",
      high_stress: true,
      email_payload: EMAIL_PAYLOAD,
    }),
  });

  assert.doesNotThrow(() => gas.onFormSubmit(FORM_EVENT));
  assert.equal(sent.length, 1, "結果メールは送信済み");
  assert.equal(ss.sheets["高ストレス者"].rows.length, 2, "記録も行われる");
});
