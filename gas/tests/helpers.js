"use strict";

/**
 * GAS テスト共通ハーネス
 *
 * GAS のグローバルサービス（PropertiesService / SpreadsheetApp / Logger 等）を
 * モックとして注入した関数スコープで .gs ファイルを評価し、
 * テスト対象の関数を取り出す。
 */

const fs = require("node:fs");
const path = require("node:path");

const GAS_DIR = path.join(__dirname, "..");

/** 複数の .gs ファイルを GAS と同様に単一グローバルスコープとして連結する */
function readGasSource(...filenames) {
  return filenames
    .map((name) => fs.readFileSync(path.join(GAS_DIR, name), "utf8"))
    .join("\n;\n");
}

function createMockSheet(existingRows) {
  const rows = existingRows ? existingRows.map((r) => r.slice()) : [];
  return {
    rows,
    getLastRow() { return rows.length; },
    appendRow(row) { rows.push(row); },
    clearContents() { rows.length = 0; },
    getDataRange() {
      return { getValues: () => rows.map((r) => r.slice()) };
    },
  };
}

function createMockSpreadsheet(sheets) {
  const registry = sheets || {};
  return {
    sheets: registry,
    getSheetByName(name) { return registry[name] || null; },
    insertSheet(name) {
      registry[name] = createMockSheet();
      return registry[name];
    },
  };
}

/**
 * .gs ソースをモック注入済みスコープで評価し、exportNames の関数を返す
 * @param {string}   source      - readGasSource() で読んだ .gs ソース
 * @param {string[]} exportNames - 取り出すグローバル関数名
 * @param {Object}   overrides   - { scriptProperties, SpreadsheetApp } を上書き
 */
function loadGas(source, exportNames, overrides = {}) {
  const scriptProps = overrides.scriptProperties || {};
  const mocks = {
    Logger: { log() {} },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (key) =>
          key in scriptProps ? scriptProps[key] : null,
      }),
    },
    SpreadsheetApp: overrides.SpreadsheetApp || {
      openById() { throw new Error("openById is not mocked"); },
      getActiveSpreadsheet() { return null; },
    },
    FormApp: {},
    ScriptApp: {},
    UrlFetchApp: {},
    GmailApp: {},
    Utilities: {},
  };
  const factory = new Function(
    ...Object.keys(mocks),
    source + "\nreturn { " + exportNames.join(", ") + " };"
  );
  return factory(...Object.values(mocks));
}

module.exports = { readGasSource, createMockSheet, createMockSpreadsheet, loadGas };
