// utils/index.ts (または適切なユーティリティファイル)

import { PC } from '@/types/pc';

/**
 * PCのステータスを日本語で表示する
 * @param status - PCのステータス (PC型定義に基づく英語)
 * @returns 日本語のステータス名
 */
export const getStatusDisplay = (status: PC['status']): string => {
  switch (status) {
    case 'available':
      return '未使用';
    case 'assigned':
      return '使用中';
    case 'returned':
      return '返却済み';
    case 'maintenance':
      return '保守中';
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
    case 'available':
      return 'bg-yellow-100 text-yellow-800'; // 未使用
    case 'assigned':
      return 'bg-green-100 text-green-800'; // 使用中
    case 'returned':
      return 'bg-red-100 text-red-800'; // 返却済み
    case 'maintenance':
      return 'bg-blue-100 text-blue-800'; // 保守中
    default:
      return 'bg-gray-100 text-gray-800';
  }
};