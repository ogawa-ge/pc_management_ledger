// utils/index.ts (または適切なユーティリティファイル)

import { PC } from '@/types/pc';

/**
 * PCのステータスを日本語で表示する
 * @param status - PCのステータス (PC型定義に基づく英語)
 * @returns 日本語のステータス名
 */
export const getStatusDisplay = (status: PC['status']): string => {
  switch (status) {
    case 'Unused':
      return '未使用';
    case 'InUse':
      return '利用中';
    case 'PendingDisposal':
      return '廃棄待ち';
    case 'Disposed':
      return '廃棄済み';
    default:
      return '不明';
  }
};

/**
 * PCのステータスに応じたCSSクラスを返す
 * @param status - PCのステータス (PC型定義に基づく英語)
 * @returns Tailwind CSSクラス文字列
 */
export const getStatusColor = (status: PC['status']): string => {
  switch (status) {
    case 'Unused':
      return 'bg-green-100 text-green-800';
    case 'InUse':
      return 'bg-blue-100 text-blue-800';
    case 'PendingDisposal':
      return 'bg-yellow-100 text-yellow-800';
    case 'Disposed':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};