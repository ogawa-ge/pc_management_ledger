// PC関連のAPI呼び出しを処理するサービス
import { PC } from '@/types/pc';
import { User } from '@/types/user';

export interface RetryState {
  status: 'idle' | 'starting' | 'processing' | 'timeout';
  waitedSeconds: number;
  remainingSeconds: number;
}

export interface RetryOptions {
  idempotencyKey?: string;
  signal?: AbortSignal;
  onRetryStateChange?: (state: RetryState) => void;
}

export interface PcReturnResponse {
  status?: string;
  message: string;
  recordId?: string;
}

const MAX_RETRY_SECONDS = 180;

const createIdempotencyKey = (): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const sleep = (milliseconds: number, signal?: AbortSignal): Promise<void> =>
  new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal?.addEventListener('abort', () => {
      window.clearTimeout(timer);
      reject(new DOMException('Request was cancelled', 'AbortError'));
    }, { once: true });
  });

const parseRetryAfter = (response: Response, fallback: number): number => {
  const parsed = Number(response.headers.get('Retry-After'));
  return Number.isFinite(parsed) && parsed > 0 && parsed <= 30 ? parsed : fallback;
};

const requestWithRetry = async <T>(
  url: string,
  init: RequestInit,
  options: RetryOptions = {},
): Promise<T> => {
  const startedAt = Date.now();
  const method = (init.method || 'GET').toUpperCase();
  const idempotencyKey = options.idempotencyKey || createIdempotencyKey();
  const headers = new Headers(init.headers);
  headers.set('Idempotency-Key', idempotencyKey);
  const fixedInit: RequestInit = { ...init, method, headers, signal: options.signal };

  while (true) {
    const response = await fetch(url, fixedInit);
    let responseBody: unknown;
    try {
      responseBody = await response.clone().json();
    } catch {
      responseBody = undefined;
    }
    const bodyStatus = typeof responseBody === 'object' && responseBody !== null && 'status' in responseBody
      ? String((responseBody as { status: unknown }).status)
      : '';
    const isStarting = response.status === 503 && bodyStatus === 'starting';
    const isProcessing = response.status === 409 && bodyStatus === 'processing';
    if (!isStarting && !isProcessing) {
      options.onRetryStateChange?.({ status: 'idle', waitedSeconds: 0, remainingSeconds: MAX_RETRY_SECONDS });
      if (!response.ok) await throwApiError(response);
      return responseBody as T;
    }

    const waitedSeconds = Math.floor((Date.now() - startedAt) / 1000);
    if (waitedSeconds >= MAX_RETRY_SECONDS) {
      options.onRetryStateChange?.({ status: 'timeout', waitedSeconds, remainingSeconds: 0 });
      throw new ApiError('バックエンドの起動が3分以内に完了しませんでした。操作は完了していません。', 503, 'start_timeout');
    }
    options.onRetryStateChange?.({
      status: isStarting ? 'starting' : 'processing',
      waitedSeconds,
      remainingSeconds: Math.max(0, MAX_RETRY_SECONDS - waitedSeconds),
    });
    await sleep(parseRetryAfter(response, isStarting ? 15 : 3) * 1000, options.signal);
  }
};

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

// PCスペック解析
export const parseSpecs = async (specsText: string, options: RetryOptions = {}) => {
  try {
    return await requestWithRetry('/api/pcs/parse-specs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ specsText }),
    }, options);
  } catch (error) {
    console.error('スペック解析エラー:', error);
    throw error;
  }
};

// PC登録
export const registerPC = async (ownerId: string, specsText: string, pcType: string = "N", userId?: string, options: RetryOptions = {}) => {
  try {
    return await requestWithRetry('/api/pcs', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(userId ? { Authorization: `Bearer ${userId}` } : {}),
      },
      body: JSON.stringify({ ownerId, specsText, pcType }),
    }, options);
  } catch (error) {
    console.error('PC登録エラー:', error);
    throw error;
  }
};

// PC一覧取得
export const getPCs = async (status?: string, options: RetryOptions = {}) => {
  try {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return await requestWithRetry<PC[]>(`/api/pcs${query}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }, options);
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
export const returnPC = async (
  pcId: string,
  returnData: { userId: string; returnReason: string; pcStatusAtReturn: string },
  options: RetryOptions = {},
) => {
  try {
    return await requestWithRetry<PcReturnResponse>(`/api/pcs/${pcId}/return`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(returnData),
    }, options);
  } catch (error) {
    console.error('PC返却エラー:', error);
    throw error;
  }
};