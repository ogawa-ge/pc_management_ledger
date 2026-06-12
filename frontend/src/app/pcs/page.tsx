'use client';

import React, { useState, useEffect } from 'react';
import { PC } from '@/types/pc';
import Link from 'next/link';
import { getStatusDisplay, getStatusColor } from '@/lib/utils';
import { signOut } from 'next-auth/react';
import { Button } from '@/components/ui/button';

// 型定義のインポートを想定
// 実際には、PCのデータ構造に合わせて調整が必要です。
interface PcsPageProps {
  // サーバーサイドレンダリングでデータを渡すことを想定
  initialPcs?: PC[];
}

const PcsPage: React.FC<PcsPageProps> = ({ initialPcs = [] }) => {
  const [pcsList, setPcsList] = useState<PC[]>(initialPcs);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPcs = async () => {
      setLoading(true);
      try {
        // API呼び出し (T029で実装した /api/pcs を想定)
        const response = await fetch('/api/pcs');
        if (!response.ok) {
          throw new Error('Failed to fetch PC list');
        }
        const data: PC[] = await response.json();
        setPcsList(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'PC一覧の取得に失敗しました。');
      } finally {
        setLoading(false);
      }
    };
    fetchPcs();
  }, []);

  if (loading) {
    return <div className="p-8 text-center">PC一覧を読み込み中です...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-600">エラーが発生しました: {error}</div>;
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">PC管理台帳 - 全PC一覧</h1>
        <Button 
          variant="outline" 
          onClick={() => signOut({ callbackUrl: '/login' })}
          className="text-red-600 border-red-600 hover:bg-red-50"
        >
          ログアウト
        </Button>
      </div>
      
      <div className="flex justify-between items-center mb-6">
        <button
          onClick={() => alert('CSVダウンロード機能が実装されます (T031)')}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-150"
        >
          CSVダウンロード
        </button>
        {/* T032でレイアウト調整されることを想定 */}
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr className="text-xs uppercase tracking-wider text-gray-500">
              <th className="px-6 py-3 text-left">管理番号</th>
              <th className="px-6 py-3 text-left">ユーザー</th>
              <th className="px-6 py-3 text-left">モデル名</th>
              <th className="px-6 py-3 text-left">ステータス</th>
              <th className="px-6 py-3 text-left">操作</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {pcsList.length > 0 ? (
              pcsList.map((pc) => (
                <tr key={pc.pcId}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{pc.pcId}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.ownerName || '未割り当て'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.modelName}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      getStatusColor(pc.status)
                    }`}>
                      {getStatusDisplay(pc.status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <Link href={`/pcs/${pc.pcId}`} className="text-indigo-600 hover:text-indigo-900">詳細</Link>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-gray-500">登録されているPCはありません。</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PcsPage;