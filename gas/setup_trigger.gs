/**
 * ストレスチェック Google Apps Script
 *
 * 役割:
 *   1. Googleフォーム送信をトリガーに Python API を呼び出す
 *   2. APIからPDFのbase64データを受け取る
 *   3. GmailApp.sendEmail() で結果PDFを受検者に送信する
 *
 * 設定:
 *   スクリプトプロパティ（ファイル > プロジェクトのプロパティ > スクリプトのプロパティ）に
 *   以下のキーを設定してください:
 *     API_URL     : PythonバックエンドのURL（例: https://your-app.run.app/run-stress-check）
 *     FORM_ID     : GoogleフォームのID（スプレッドシートに紐づく場合は不要）
 *
 * トリガー設定:
 *   setupTrigger() を一度だけ手動実行すると onFormSubmit が自動登録されます。
 */

// ── 定数 ────────────────────────────────────────────────────────

var SENDER_EMAIL = "epiphanypsycho@gmail.com";

// フォームの質問タイトル → APIフィールド名のマッピング
// ※ 実際のフォームの質問タイトルに合わせて修正してください
var FIELD_MAP = {
  "お名前":       "name",
  "メールアドレス": "email",
  "所属部署":     "department",
  "性別":        "gender",
  "年齢区分":     "age_group",
  "雇用形態":     "employment_type",
};

// Q1〜Q57 の質問タイトルプレフィックス（例: "Q1", "問1" 等）
var Q_PREFIX = "Q";   // フォームの質問タイトルが "Q1", "Q2", ... の場合


// ── トリガー登録 ─────────────────────────────────────────────────

/**
 * onFormSubmit トリガーをプログラムから登録する
 * 一度だけ手動実行してください（重複登録を防ぐため既存トリガーを削除してから登録）
 */
function setupTrigger() {
  var props  = PropertiesService.getScriptProperties();
  var formId = props.getProperty("FORM_ID");

  // 既存の onFormSubmit トリガーを削除
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === "onFormSubmit") {
      ScriptApp.deleteTrigger(t);
    }
  });

  var form;
  if (formId) {
    // スクリプトプロパティに FORM_ID が設定されている場合
    form = FormApp.openById(formId);
    Logger.log("FORM_ID からフォームを取得: " + formId);
  } else {
    // スプレッドシートにバインドされたフォームから取得
    var ss      = SpreadsheetApp.getActiveSpreadsheet();
    var formUrl = ss.getFormUrl();
    if (!formUrl) {
      throw new Error(
        "スプレッドシートにフォームが紐づいていません。" +
        "スクリプトプロパティ FORM_ID を設定するか、" +
        "フォームの回答先としてこのスプレッドシートを指定してください。"
      );
    }
    form = FormApp.openByUrl(formUrl);
    Logger.log("スプレッドシートにバインドされたフォームを取得: " + formUrl);
  }

  ScriptApp.newTrigger("onFormSubmit")
    .forForm(form)
    .onFormSubmit()
    .create();
  Logger.log("フォームトリガー登録完了");
}


// ── メインハンドラ ────────────────────────────────────────────────

/**
 * フォーム送信時に呼ばれるトリガー関数
 * @param {Object} e - フォーム送信イベントオブジェクト
 */
function onFormSubmit(e) {
  try {
    var payload = _buildApiPayload(e);
    Logger.log("API送信開始: " + payload.response_id);

    var result = _callApi(payload);

    if (result.status === "success" || result.status === "partial") {
      if (result.email_payload) {
        _sendEmail(result.email_payload);
        Logger.log("メール送信完了: " + result.email_payload.to);
      } else {
        Logger.log("email_payload なし（メールアドレス未入力または PDF 生成失敗）");
      }
    } else {
      Logger.log("API エラー: " + JSON.stringify(result.errors));
    }

  } catch (err) {
    Logger.log("onFormSubmit エラー: " + err.toString());
    // 必要に応じて管理者へ通知
    // MailApp.sendEmail("admin@example.com", "ストレスチェックエラー", err.toString());
  }
}


// ── API 呼び出し ──────────────────────────────────────────────────

/**
 * Python バックエンドを呼び出す
 * @param {Object} payload - リクエストボディ
 * @returns {Object} - APIレスポンス（パース済みJSON）
 */
function _callApi(payload) {
  var props  = PropertiesService.getScriptProperties();
  var apiUrl = props.getProperty("API_URL");

  if (!apiUrl) {
    throw new Error("スクリプトプロパティ API_URL が設定されていません");
  }

  var options = {
    method:      "post",
    contentType: "application/json",
    payload:     JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  var response    = UrlFetchApp.fetch(apiUrl, options);
  var statusCode  = response.getResponseCode();
  var responseText = response.getContentText();

  Logger.log("API レスポンス [" + statusCode + "]: " + responseText.substring(0, 200));

  if (statusCode >= 500) {
    throw new Error("API サーバーエラー (" + statusCode + "): " + responseText);
  }

  return JSON.parse(responseText);
}


// ── メール送信 ────────────────────────────────────────────────────

/**
 * APIから受け取った email_payload を使って GmailApp でメール送信する
 * @param {Object} emailPayload - run_single() が返す email_payload
 *   {
 *     to:           string,  // 送付先
 *     subject:      string,  // 件名
 *     body:         string,  // 本文
 *     pdf_base64:   string,  // PDFのBase64
 *     pdf_filename: string,  // 添付ファイル名
 *   }
 */
function _sendEmail(emailPayload) {
  var pdfBytes = Utilities.base64Decode(emailPayload.pdf_base64);
  var pdfBlob  = Utilities.newBlob(pdfBytes, "application/pdf", emailPayload.pdf_filename);

  GmailApp.sendEmail(
    emailPayload.to,
    emailPayload.subject,
    emailPayload.body,
    {
      from:        SENDER_EMAIL,
      attachments: [pdfBlob],
    }
  );
}


// ── フォーム回答のパース ──────────────────────────────────────────

/**
 * フォーム送信イベントから API 送信用ペイロードを組み立てる
 * @param {Object} e - フォーム送信イベント
 * @returns {Object} - APIペイロード
 */
function _buildApiPayload(e) {
  var answers  = {};
  var meta     = {};
  var responses = e.response ? e.response.getItemResponses() : e.namedValues;

  // getItemResponses() 形式（フォーム直接バインド）
  if (e.response) {
    e.response.getItemResponses().forEach(function(item) {
      var title = item.getItem().getTitle().trim();
      var value = item.getResponse();

      if (FIELD_MAP[title]) {
        meta[FIELD_MAP[title]] = value;
      } else if (_isQuestionItem(title)) {
        var qNum = _extractQNum(title);
        if (qNum) answers["Q" + qNum] = Number(value);
      }
    });

  // namedValues 形式（スプレッドシートバインド）
  } else {
    Object.keys(e.namedValues).forEach(function(title) {
      var value = e.namedValues[title][0];
      var key   = title.trim();

      if (FIELD_MAP[key]) {
        meta[FIELD_MAP[key]] = value;
      } else if (_isQuestionItem(key)) {
        var qNum = _extractQNum(key);
        if (qNum) answers["Q" + qNum] = Number(value);
      }
    });
  }

  return {
    response_id:     _generateId(),
    company_code:    _getCompanyCode(),
    name:            meta.name            || "",
    email:           meta.email           || "",
    department:      meta.department      || "",
    gender:          meta.gender          || "",
    age_group:       meta.age_group       || "",
    employment_type: meta.employment_type || "",
    answers:         answers,
    version:         "57",
    submitted_at:    new Date().toISOString(),
  };
}

/** "Q1", "Q57", "問1" 等の質問タイトルか判定 */
function _isQuestionItem(title) {
  return /^[QqＱ問]\d+/.test(title);
}

/** "Q12" → 12 を返す */
function _extractQNum(title) {
  var m = title.match(/\d+/);
  return m ? parseInt(m[0], 10) : null;
}

/** タイムスタンプベースの簡易ID */
function _generateId() {
  return "GAS-" + new Date().getTime();
}

/** スクリプトプロパティから企業コードを取得 */
function _getCompanyCode() {
  return PropertiesService.getScriptProperties().getProperty("COMPANY_CODE") || "UNKNOWN";
}


// ── 手動テスト用 ──────────────────────────────────────────────────

/**
 * ダミーデータで onFormSubmit の動作を確認する
 * GAS エディタから直接実行してテストできます
 */
function testOnFormSubmit() {
  var dummyAnswers = {};
  for (var i = 1; i <= 57; i++) {
    dummyAnswers["Q" + i] = (i % 4) + 1;
  }

  var fakeEvent = {
    namedValues: Object.assign(
      {
        "お名前":       ["テスト 太郎"],
        "メールアドレス": ["test@example.com"],
        "所属部署":     ["開発部"],
        "性別":        ["男性"],
        "年齢区分":     ["30〜39歳"],
        "雇用形態":     ["正社員"],
      },
      Object.fromEntries(
        Object.entries(dummyAnswers).map(function(kv) {
          return [kv[0], [String(kv[1])]];
        })
      )
    ),
  };

  onFormSubmit(fakeEvent);
  Logger.log("testOnFormSubmit 完了");
}
