// PC関連のAPI呼び出しを処理するサービス
import { PC } from '@/types/pc';

// PCスペック解析
export const parseSpecs = async (specsText: string) => {
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

// PC登録
export const registerPC = async (ownerId: string, specsText: string, pcType: string = "N") => {
  try {
    const response = await fetch('/api/pcs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ownerId, specsText, pcType }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
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
export const getUsers = async () => {
  try {
    const response = await fetch('/api/users', {
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