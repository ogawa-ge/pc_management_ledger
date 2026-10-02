// PC関連のAPI呼び出しを処理するサービス
import { PC } from '@/types/pc';
import { User } from '@/types/user';

// Gemini APIによる抽出結果（parse-specsのレスポンス）
export interface PcSpecs {
  cpu?: string | null;
  memory?: string | number | null;
  storage?: string | number | null;
  os?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  gpu?: string | null;
  pcName?: string | null;
}

// parse-specsが失敗した場合のレスポンス（FR-007: 3回リトライ後もエラーの場合 retriesExhausted が true になる）
export interface PcSpecsError {
  error: string;
  retriesExhausted?: boolean;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const throwApiError = async (response: Response): Promise<never> => {
  let detail: string | undefined;
  try {
    const body = await response.json();
    detail = typeof body.detail === 'string' ? body.detail : undefined;
  } catch {
    detail = undefined;
  }
  throw new ApiError(detail || `HTTP error! status: ${response.status}`, response.status, detail);
};

// PCスペック解析（貼り付けられたターミナル出力からAIで抽出、DBへの書き込みは行わない）
export const parseSpecs = async (specsText: string): Promise<PcSpecs | PcSpecsError> => {
  try {
    const response = await fetch('/api/pcs/parse-specs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ specsText }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('スペック解析エラー:', error);
    throw error;
  }
};

// PC登録（specsはクライアント側で確定済み（抽出結果 or 手動編集後）の構造化フィールド）
export const registerPC = async (ownerId: string, specs: PcSpecs, pcType: string = "N", userId?: string) => {
  try {
    const response = await fetch('/api/pcs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(userId ? { Authorization: `Bearer ${userId}` } : {}),
      },
      body: JSON.stringify({ ownerId, pcType, ...specs }),
    });

    if (!response.ok) {
      await throwApiError(response);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('PC登録エラー:', error);
    throw error;
  }
};

// PC一覧取得
export const getPCs = async () => {
  try {
    const response = await fetch('/api/pcs', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('PC一覧取得エラー:', error);
    throw error;
  }
};

// ユーザー一覧取得
export const getUsers = async (userId: string): Promise<User[]> => {
  try {
    const response = await fetch('/api/users', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${userId}`,
      },
    });

    if (!response.ok) {
      await throwApiError(response);
    }

    const result: User[] = await response.json();
    return result;
  } catch (error) {
    console.error('ユーザー一覧取得エラー:', error);
    throw error;
  }
};

// PC返却
export const returnPC = async (pcId: string, returnData: { returnDate: string; returnReason: string; condition: string }) => {
  try {
    const response = await fetch(`/api/pcs/${pcId}/return`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(returnData),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error('PC返却エラー:', error);
    throw error;
  }
};