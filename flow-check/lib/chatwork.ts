/**
 * Chatworkへの新規回答通知。
 *
 * 通知はあくまで補助機能。失敗・未設定でも回答者のフローを止めない（fail open）。
 */

/** 管理画面のベースURL。独自ドメインに移行した場合は環境変数で上書きできる */
const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://flow-check-eta.vercel.app";

const CHATWORK_TIMEOUT_MS = 3000;

export interface NewResponseNotification {
  companyName: string;
  name: string;
  position: string;
  industry: string;
  employeeCount: string;
  leadSource: string;
  /** 回答日時（UTCのISO 8601文字列） */
  completedAt: string;
  sessionId: string;
}

/** UTCのISO文字列を JST の "YYYY-MM-DD HH:mm" に変換する */
export function toJstDisplay(isoUtc: string): string {
  const jst = new Date(new Date(isoUtc).getTime() + 9 * 60 * 60 * 1000);
  return jst.toISOString().replace("T", " ").slice(0, 16);
}

/**
 * 通知メッセージを組み立てる。
 * メールアドレス・電話番号は意図的に含めない（通知に個人連絡先を流さない）。
 */
export function buildNewResponseMessage(
  notification: NewResponseNotification
): string {
  return [
    "[Flow Check] 新しい回答が届きました",
    "",
    `会社名：${notification.companyName}`,
    `氏名：${notification.name}`,
    `役職：${notification.position}`,
    `業種：${notification.industry}`,
    `従業員数：${notification.employeeCount}`,
    `きっかけ：${notification.leadSource}`,
    `回答日時：${toJstDisplay(notification.completedAt)}（JST）`,
    "",
    `管理画面：${SITE_URL}/admin/responses/${notification.sessionId}`,
  ].join("\n");
}

/**
 * 新規回答をChatworkへ通知する。
 * 環境変数が未設定なら何もしない。例外は投げない。
 */
export async function notifyNewResponse(
  notification: NewResponseNotification
): Promise<void> {
  const apiToken = process.env.CHATWORK_API_TOKEN;
  const roomId = process.env.CHATWORK_ROOM_ID;
  if (!apiToken || !roomId) return;

  try {
    const message = buildNewResponseMessage(notification);
    const response = await fetch(
      `https://api.chatwork.com/v2/rooms/${roomId}/messages`,
      {
        method: "POST",
        headers: {
          "X-ChatWorkToken": apiToken,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: `body=${encodeURIComponent(message)}`,
        // Vercelの関数タイムアウトに巻き込まれないよう上限を設ける
        signal: AbortSignal.timeout(CHATWORK_TIMEOUT_MS),
      }
    );
    if (!response.ok) {
      console.error(
        "chatwork notify failed:",
        response.status,
        await response.text().catch(() => "")
      );
    }
  } catch (error) {
    // 通知失敗は握りつぶす（回答の保存は完了しているため）
    console.error("chatwork notify failed:", error);
  }
}
