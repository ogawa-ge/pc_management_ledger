/**
 * 認証関連のサービス関数
 */

/**
 * ユーザーの権限を取得する
 * @param userId - ユーザーID
 * @returns ユーザーの権限の配列
 */
export async function get_user_permissions(userId: string): Promise<string[]> {
  try {
    // サーバーサイドでの実行時は絶対パスが必要なため、バックエンドのURLを直接使用
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || '';
    const apiUrl = `${baseUrl}/api/auth/user-permissions`;
    
    // APIエンドポイントからユーザー権限を取得
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
    return data.permissions || [];
  } catch (error) {
    console.error('権限の取得に失敗しました:', error);
    return [];
  }
}