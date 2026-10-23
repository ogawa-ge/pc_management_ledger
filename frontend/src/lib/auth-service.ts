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

export interface SyncUserRequest {
  userId: string;
  email: string;
  name?: string | null;
}

export interface SyncUserResult {
  userId: string;
  role: 'Admin' | 'User';
  created: boolean;
}

/**
 * ログイン時に Users へユーザーを登録（登録済みなら更新）する
 * 失敗した場合はログインを拒否するため、例外をそのまま投げる
 * @param request - Google のユーザー情報（sub、email、name）
 * @returns 登録結果（ロール、新規作成かどうか）
 */
export async function syncUser({ userId, email, name }: SyncUserRequest): Promise<SyncUserResult> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const response = await fetch(`${baseUrl}/api/auth/sync-user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ userId, email, name: name ?? null }),
  });

  if (!response.ok) {
    throw new Error(`ユーザー登録に失敗しました (status: ${response.status})`);
  }

  return response.json();
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
