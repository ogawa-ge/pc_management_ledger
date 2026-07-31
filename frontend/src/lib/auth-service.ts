/**
 * 認証関連のサービス関数
 */

/**
 * ユーザーの権限を取得する
 * @param userId - ユーザーID
 * @returns ユーザーの権限の配列
 */
export interface UserAuthInfo {
  permissions: string[];
  role: string;
}

/**
 * ユーザーの認証情報（権限、ロール）を取得する
 * @param userId - ユーザーID
 * @returns ユーザーの認証情報
 */
export async function get_user_auth_info(userId: string): Promise<UserAuthInfo> {
  try {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';
    const apiUrl = `${baseUrl}/api/auth/user-permissions`;
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ userId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      permissions: data.permissions || [],
      role: data.role || 'User'
    };
  } catch (error) {
    console.error('ユーザー認証情報の取得に失敗しました:', error);
    return { permissions: [], role: 'User' };
  }
}

/**
 * ユーザーの権限を取得する
 * @param userId - ユーザーID
 * @returns ユーザーの権限の配列
 */
export async function get_user_permissions(userId: string): Promise<string[]> {
  const info = await get_user_auth_info(userId);
  return info.permissions;
}
