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
