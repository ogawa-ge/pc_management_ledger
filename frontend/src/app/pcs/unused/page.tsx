import React, { useState, useEffect } from 'react';
import { PC } from '@/types/pc';
import Link from 'next/link';
import { getStatusDisplay, getStatusColor } from '@/lib/utils';

interface UnusedPcsPageProps {
  initialPcs?: PC[];
}

const UnusedPcsPage: React.FC<UnusedPcsPageProps> = ({ initialPcs = [] }) => {
  const [pcsList, setPcsList] = useState<PC[]>(initialPcs);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUnusedPcs = async () => {
      setLoading(true);
      try {
        // ステータスが「未使用」の PC のみを取得
        const response = await fetch('/api/pcs?status=Unused');
        if (!response.ok) {
          throw new Error('Failed to fetch unused PC list');
        }
        const data: PC[] = await response.json();
        setPcsList(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : '未使用 PC 一覧の取得に失敗しました。');
      } finally {
        setLoading(false);
      }
    };
    fetchUnusedPcs();
  }, []);

  if (loading) {
    return <div className="p-8 text-center">未使用 PC 一覧を読み込み中です...</div>;
  }

  if (error) {
    return <div className="p-8 text-red-600">エラーが発生しました：{error}</div>;
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">未使用 PC 一覧</h1>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr className="text-xs uppercase tracking-wider text-gray-500">
              <th className="px-6 py-3 text-left">管理番号</th>
              <th className="px-6 py-3 text-left">タイプ</th>
              <th className="px-6 py-3 text-left">メーカー</th>
              <th className="px-6 py-3 text-left">モデル</th>
              <th className="px-6 py-3 text-left">CPU</th>
              <th className="px-6 py-3 text-left">メモリ</th>
              <th className="px-6 py-3 text-left">ストレージ</th>
              <th className="px-6 py-3 text-left">OS</th>
              <th className="px-6 py-3 text-left">登録日</th>
              <th className="px-6 py-3 text-left">操作</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {pcsList.length > 0 ? (
              pcsList.map((pc) => (
                <tr key={pc.pcId}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{pc.pcId}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.type}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.manufacturer}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.model}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.cpu}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.memory}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.storage}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{pc.os}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{new Date(pc.createdAt).toLocaleDateString('ja-JP')}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <Link
                      href={`/pcs/${pc.pcId}`}
                      className="text-indigo-600 hover:text-indigo-900"
                    >
                      詳細
                    </Link>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={10} className="px-6 py-4 text-center text-gray-500">
                  未使用の PC はありません。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default UnusedPcsPage;
