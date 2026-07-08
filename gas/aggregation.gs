/**
 * ストレスチェック 集団分析 Google Apps Script
 *
 * 役割:
 *   フォーム回答シート（母数）と「高ストレス者」シート（分子）から
 *   部署別の集団分析（n・高ストレス者数・高ストレス率）を計算し、
 *   「集団分析」シートに出力する。
 *
 *   Python 側 main.py の _calc_group_summary() と同じ規則で、
 *   MIN_GROUP_SIZE（既定10名）未満の部署は個人特定防止のため
 *   数値を非表示（suppressed）にする。
 *
 * 設定（スクリプトプロパティ）:
 *   RESPONSES_SHEET_ID      : フォーム回答が蓄積されるスプレッドシートのID
 *                             （未設定の場合はバインドされたスプレッドシート）
 *   RESPONSES_SHEET_NAME    : 回答シート名（未設定の場合は「フォームの回答 1」）
 *   HIGH_STRESS_SHEET_ID    : 高ストレス者記録シートのID（setup_trigger.gs と共通）
 *   GROUP_ANALYSIS_SHEET_ID : 集団分析の出力先スプレッドシートのID
 *                             （未設定の場合はバインドされたスプレッドシート）
 *   MIN_GROUP_SIZE          : 集計を表示する最小人数（未設定の場合は10）
 *
 * 実行方法:
 *   runGroupAnalysis() を GAS エディタから手動実行するか、
 *   時間主導型トリガー（例: 毎日深夜）に登録してください。
 */

// ── 定数 ────────────────────────────────────────────────────────

var GROUP_ANALYSIS_SHEET_NAME = "集団分析";
var DEFAULT_RESPONSES_SHEET_NAME = "フォームの回答 1";
var DEFAULT_MIN_GROUP_SIZE = 10;


// ── エントリポイント ─────────────────────────────────────────────

/**
 * 集団分析を実行し「集団分析」シートに出力する
 * @returns {Object[]} 部署別の集計結果（テスト・ログ用）
 */
function runGroupAnalysis() {
  var props = PropertiesService.getScriptProperties();
  var minGroupSize =
    parseInt(props.getProperty("MIN_GROUP_SIZE"), 10) || DEFAULT_MIN_GROUP_SIZE;

  var respondents = _readRespondents();
  var hsRecords   = _readHighStressRecords();

  var rows = _aggregateGroups(respondents, hsRecords, minGroupSize);
  _writeGroupAnalysis(rows);

  Logger.log(
    "集団分析完了: " + rows.length + "部署 / 回答者" + respondents.length + "名"
  );
  return rows;
}


// ── 集計ロジック（純関数） ────────────────────────────────────────

/**
 * 部署別に集団分析を計算する
 * @param {Object[]} respondents      - 全回答者 [{department, email}, ...]
 * @param {Object[]} highStressRecords - 高ストレス者 [{department, email, response_id}, ...]
 * @param {number}   minGroupSize     - この人数未満の部署は数値を非表示にする
 * @returns {Object[]} [{department, n, suppressed, high_stress_count, high_stress_rate}, ...]
 */
function _aggregateGroups(respondents, highStressRecords, minGroupSize) {
  // 同一人物の重複回答は最新のみ採用する
  var uniqueRespondents = _dedupeByKey(respondents, function (r) {
    return r.email;
  });
  var uniqueHighStress = _dedupeByKey(highStressRecords, function (r) {
    return r.email || r.response_id;
  });

  var counts = {};
  uniqueRespondents.forEach(function (r) {
    var dept = r.department || "";
    counts[dept] = (counts[dept] || 0) + 1;
  });

  var hsCounts = {};
  uniqueHighStress.forEach(function (r) {
    var dept = r.department || "";
    hsCounts[dept] = (hsCounts[dept] || 0) + 1;
  });

  // 回答シートに存在しない部署が高ストレス記録にある場合は集計不能（母数不明）
  Object.keys(hsCounts).forEach(function (dept) {
    if (!(dept in counts)) {
      Logger.log(
        "警告: 部署「" + dept + "」は高ストレス記録のみ存在するため集計から除外します"
      );
    }
  });

  return Object.keys(counts).sort().map(function (dept) {
    var n = counts[dept];
    var suppressed = n < minGroupSize;
    var hsCount = hsCounts[dept] || 0;
    return {
      department: dept,
      n: n,
      suppressed: suppressed,
      // 個人特定防止：少人数部署はスコアを非表示（Python 側と同じ規則）
      high_stress_count: suppressed ? null : hsCount,
      high_stress_rate: suppressed ? null : Math.round((hsCount / n) * 1000) / 10,
    };
  });
}

/**
 * keyFn が返すキーで重複を除去する（後勝ち＝最新の記録を採用）
 * キーが空の記録は重複判定せずそのまま残す
 */
function _dedupeByKey(records, keyFn) {
  var indexByKey = {};
  var result = [];
  records.forEach(function (rec) {
    var key = keyFn(rec);
    if (!key) {
      result.push(rec);
    } else if (indexByKey[key] === undefined) {
      indexByKey[key] = result.length;
      result.push(rec);
    } else {
      result[indexByKey[key]] = rec;
    }
  });
  return result;
}


// ── データ読み込み ────────────────────────────────────────────────

/**
 * フォーム回答シートから全回答者の {department, email} を読み込む
 */
function _readRespondents() {
  var props = PropertiesService.getScriptProperties();
  var ss = _openSpreadsheetByProp("RESPONSES_SHEET_ID");
  var sheetName =
    props.getProperty("RESPONSES_SHEET_NAME") || DEFAULT_RESPONSES_SHEET_NAME;

  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    throw new Error(
      "回答シート「" + sheetName + "」が見つかりません。" +
      "スクリプトプロパティ RESPONSES_SHEET_NAME を確認してください。"
    );
  }
  return _readRows(sheet, { department: "所属部署", email: "メールアドレス" });
}

/**
 * 「高ストレス者」シート（setup_trigger.gs の _recordHighStress が書き込む）から
 * {department, email, response_id} を読み込む。シート未作成なら空配列を返す。
 */
function _readHighStressRecords() {
  var ss = _openSpreadsheetByProp("HIGH_STRESS_SHEET_ID");
  var sheet = ss.getSheetByName(HIGH_STRESS_SHEET_NAME);
  if (!sheet) {
    return []; // まだ高ストレス者が記録されていない
  }
  return _readRows(sheet, {
    department:  "所属部署",
    email:       "メールアドレス",
    response_id: "response_id",
  });
}

/**
 * シートの1行目をヘッダーとして、指定した列をオブジェクトの配列で返す
 * @param {Sheet}  sheet     - 対象シート
 * @param {Object} columnMap - {キー名: ヘッダータイトル}
 */
function _readRows(sheet, columnMap) {
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) return [];

  var headers = values[0].map(function (h) {
    return String(h).trim();
  });
  var indexes = {};
  Object.keys(columnMap).forEach(function (key) {
    indexes[key] = headers.indexOf(columnMap[key]);
  });

  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var rec = {};
    Object.keys(indexes).forEach(function (key) {
      rec[key] =
        indexes[key] >= 0 ? String(values[i][indexes[key]]).trim() : "";
    });
    rows.push(rec);
  }
  return rows;
}

/**
 * スクリプトプロパティのIDでスプレッドシートを開く
 * （未設定の場合はバインドされたスプレッドシートにフォールバック）
 */
function _openSpreadsheetByProp(propKey) {
  var id = PropertiesService.getScriptProperties().getProperty(propKey);
  var ss = id
    ? SpreadsheetApp.openById(id)
    : SpreadsheetApp.getActiveSpreadsheet();
  if (!ss) {
    throw new Error(
      "スプレッドシートが見つかりません。" +
      "スクリプトプロパティ " + propKey + " を設定してください。"
    );
  }
  return ss;
}


// ── 出力 ─────────────────────────────────────────────────────────

/**
 * 集計結果を「集団分析」シートに書き出す（毎回全体を洗い替え）
 * @param {Object[]} rows - _aggregateGroups() の返り値
 */
function _writeGroupAnalysis(rows) {
  var ss = _openSpreadsheetByProp("GROUP_ANALYSIS_SHEET_ID");
  var sheet = ss.getSheetByName(GROUP_ANALYSIS_SHEET_NAME)
    || ss.insertSheet(GROUP_ANALYSIS_SHEET_NAME);

  sheet.clearContents();
  sheet.appendRow([
    "部署", "回答者数", "高ストレス者数", "高ストレス率(%)",
    "少人数のため非表示", "集計日時",
  ]);

  var now = new Date();
  rows.forEach(function (row) {
    sheet.appendRow([
      row.department,
      row.n,
      row.suppressed ? "" : row.high_stress_count,
      row.suppressed ? "" : row.high_stress_rate,
      row.suppressed,
      now,
    ]);
  });
}
