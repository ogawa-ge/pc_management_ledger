'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { PC } from '@/types/pc';
import Link from 'next/link';
import { getStatusDisplay, getStatusColor } from '@/lib/utils';
import { signOut, useSession } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';

// 型定義のインポートを想定
// 実際には、PCのデータ構造に合わせて調整が必要です。
interface PcsPageProps {
  // サーバーサイドレンダリングでデータを渡すことを想定
  initialPcs?: PC[];
}

const PcsPage: React.FC<PcsPageProps> = ({ initialPcs = [] }) => {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [pcsList, setPcsList] = useState<PC[]>(initialPcs);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStartingUp, setIsStartingUp] = useState(false);

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login');
    }
  }, [status, router]);

  const fetchPcs = useCallback(async (retryCount = 0, isManualRetry = false) => {
    if (retryCount === 0 || isManualRetry) setLoading(true);
    setError(null);
    try {
      // API呼び出し (T029で実装した /api/pcs を想定)
      const response = await fetch('/api/pcs');
      
      if (!response.ok) {
        if (!isManualRetry && response.status === 503 && retryCount < 3) {
          setIsStartingUp(true);
          setTimeout(() => {
            fetchPcs(retryCount + 1, false);
          }, 5000);
          return;
        }
        
        let errorMessage = 'PC一覧の取得に失敗しました。サーバーに一時的に接続できません。';
        if (response.status === 401 || response.status === 403) {
          errorMessage = 'アクセス権限がありません。ログイン状態を確認してください。';
        } else if (response.status >= 500) {
          errorMessage = 'サーバーでエラーが発生しました。しばらく経ってから再試行してください。';
        }
        setIsStartingUp(false);
        setError(errorMessage);
        setLoading(false);
        return;
      }
      
      const data: PC[] = await response.json();
      setPcsList(data);
      setIsStartingUp(false);
      setLoading(false);
    } catch {
      setIsStartingUp(false);
      setError('PC一覧の取得に失敗しました。サーバーに一時的に接続できません。');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status === 'authenticated') {
      fetchPcs();
    }
  }, [status, fetchPcs]);

  if (status === 'loading' || loading) {
    if (isStartingUp) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="text-gray-600 font-medium">サーバー起動中...</p>
          <p className="text-sm text-gray-400">しばらくお待ちください（最大15秒程度）</p>
        </div>
      );
    }
    return <div className="p-8 text-center">読み込み中です...</div>;
  }

  if (status === 'unauthenticated') {
    return null; // リダイレクトされるため何も表示しない
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-4 p-8 text-center">
        <p className="text-red-600 font-medium">{error}</p>
        <Button 
          onClick={() => fetchPcs(0, true)} 
          variant="outline" 
          className="border-red-600 text-red-600 hover:bg-red-50"
        >
          再試行
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold">PC管理台帳 - 全PC一覧</h1>
          {session?.user && (
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
              (session.user as any).role === 'Admin' 
                ? 'bg-red-100 text-red-800 border border-red-200' 
                : 'bg-green-100 text-green-800 border border-green-200'
            }`}>
              {(session.user as any).role === 'Admin' ? '管理者 (Admin)' : '一般ユーザー (User)'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {session?.user && (
            <span className="text-sm text-gray-600">
              {session.user.name || session.user.email}
            </span>
          )}
          <Button 
            variant="outline" 
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="text-red-600 border-red-600 hover:bg-red-50"
          >
            ログアウト
          </Button>
        </div>
      </div>
      
      <div className="flex justify-between items-center mb-6">
        <div className="flex gap-4">
          <Link href="/pcs/register">
            <Button className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition duration-150">
              PC新規登録
            </Button>
          </Link>
          <Link href="/pcs/unused">
            <Button variant="outline" className="border-blue-600 text-blue-600 hover:bg-blue-50 font-bold py-2 px-4 rounded transition duration-150">
              未使用PC一覧
            </Button>
          </Link>
          {session?.user && (session.user as any).role === 'Admin' && (
            <Button
              onClick={() => alert('CSVダウンロード機能が実装されます (T031)')}
              className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded transition duration-150"
            >
              CSVダウンロード
            </Button>
          )}
        </div>
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