export interface Profile {
  name: string;
  company_name: string;
  position: string;
  industry: string;
  employee_count: string;
  email: string;
  phone: string;
  lead_source: string;
}

/** 属性入力→診断本体の間で回答者情報を受け渡すsessionStorageキー */
export const PROFILE_STORAGE_KEY = "flow-check-profile";

/**
 * 診断本体→完了画面の間でsession_idを受け渡すsessionStorageキー。
 * 完了画面のレーダーチャート表示に使う。URLに出さないことで、
 * 結果ページのリンクが他者に共有されるのを防ぐ。
 */
export const RESULT_SESSION_STORAGE_KEY = "flow-check-session-id";
