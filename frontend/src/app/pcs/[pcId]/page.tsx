'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { PC } from '@/types/pc';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import ECSLoadingState, { useECSLoadingState } from '@/components/ecs-loading-state';
import { ApiError, getPCById, updatePCStatus } from '@/services/pc-api';
import { formatSpecValue, getPcTypeDisplay, getStatusColor, getStatusDisplay } from '@/lib/utils';

const STATUS_OPTIONS: Array<{ value: PC['status']; label: string }> = [
  { value: 'InUse', label: '利用中' },
  { value: 'Unused', label: '未使用' },
  { value: 'PendingDisposal', label: '廃棄待ち' },
  { value: 'Disposed', label: '廃棄済み' },
];

const formatDateTime = (value?: string | null): string => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('ja-JP');
};

export default function PcDetailPage() {
  const params = useParams<{ pcId: string | string[] }>();
  const rawPcId = params?.pcId;
  const pcId = Array.isArray(rawPcId) ? rawPcId[0] : rawPcId;

  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const ecsLoading = useECSLoadingState();

  const [pc, setPc] = useState<PC | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedStatus, setSelectedStatus] = useState<PC['status']>('Unused');
  const [statusReason, setStatusReason] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (sessionStatus === 'unauthenticated') {
      router.push('/login');
    }
  }, [sessionStatus, router]);

  const syncRetryState = useCallback(
    (retry: { status: 'idle' | 'starting' | 'processing' | 'timeout'; remainingSeconds: number }) => {
      ecsLoading.setStatus(retry.status === 'idle' ? 'starting' : retry.status);
      ecsLoading.setRemainingSeconds(retry.remainingSeconds);
      ecsLoading.setIsLoading(retry.status !== 'idle');
    },
    [],
  );

  const fetchPc = useCallback(async () => {
    if (!pcId) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const data = await getPCById(pcId, { onRetryStateChange: syncRetryState });
      setPc(data);
      setSelectedStatus(data.status);
    } catch (err) {
      ecsLoading.setIsLoading(false);
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setNotFound(true);
        } else if (err.status === 401 || err.status === 403) {
          setError('アクセス権限がありません。ログイン状態を確認してください。');
        } else if (err.detail === 'start_timeout') {
          setError(err.message);
        } else if (err.status >= 500) {
          setError('サーバーでエラーが発生しました。しばらく経ってから再試行してください。');
        } else {
          setError('PC詳細情報の取得に失敗しました。サーバーに一時的に接続できません。');
        }
      } else {
        setError('PC詳細情報の取得に失敗しました。サーバーに一時的に接続できません。');
      }
    } finally {
      setLoading(false);
    }
  }, [pcId, syncRetryState]);

  useEffect(() => {
    if (sessionStatus === 'authenticated') {
      fetchPc();
    }
  }, [sessionStatus, fetchPc]);

  const handleStatusUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pc || !session?.user?.id || selectedStatus === pc.status) return;

    setIsUpdatingStatus(true);
    setStatusMessage(null);

    try {
      const updated = await updatePCStatus(
        pc.pcId,
        selectedStatus,
        session.user.id,
        statusReason,
        { onRetryStateChange: syncRetryState },
      );
      setPc((prev) =>
        prev
          ? {
              ...prev,
              status: updated.newStatus,
              ownerName: updated.newStatus === 'InUse' ? prev.ownerName : null,
              updatedAt: updated.updatedAt,
            }
          : prev,
      );
      try {
        const refreshed = await getPCById(pc.pcId, { onRetryStateChange: syncRetryState });
        setPc(refreshed);
        setSelectedStatus(refreshed.status);
      } catch {
        setSelectedStatus(updated.newStatus);
      }
      setStatusReason('');
      setStatusMessage({
        type: 'success',
        text: `ステータスを「${getStatusDisplay(updated.newStatus)}」に更新しました。`,
      });
    } catch (err) {
      ecsLoading.setIsLoading(false);
      if (err instanceof ApiError) {
        if (err.status === 401 || err.status === 403) {
          setStatusMessage({ type: 'error', text: 'ステータスを更新する権限がありません。' });
        } else if (err.detail === 'start_timeout') {
          setStatusMessage({ type: 'error', text: err.message });
        } else {
          setStatusMessage({ type: 'error', text: err.message || 'ステータスの更新に失敗しました。' });
        }
      } else {
        setStatusMessage({ type: 'error', text: 'ステータスの更新中に通信エラーが発生しました。' });
      }
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  if (sessionStatus === 'loading' || loading) {
    return (
      <>
        <ECSLoadingState
          isLoading={ecsLoading.isLoading}
          status={ecsLoading.status}
          remainingSeconds={ecsLoading.remainingSeconds}
        />
        <div className="p-8 text-center">読み込み中です...</div>
      </>
    );
  }

  if (sessionStatus === 'unauthenticated') {
    return null;
  }

  if (notFound) {
    return (
      <div className="container mx-auto max-w-2xl p-8 text-center space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">PCが見つかりません</h1>
        <p className="text-gray-600">
          指定された PC（{pcId || '-'}）は見つかりませんでした。管理番号をご確認のうえ、一覧から再度選択してください。
        </p>
        <div>
          <Link href="/pcs">
            <Button variant="outline" className="">
              PC一覧に戻る
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (error || !pc) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-4 p-8 text-center">
        <p className="text-red-600 font-medium">{error || 'PC詳細情報の取得に失敗しました。'}</p>
        <div className="flex gap-3">
          <Button
            onClick={() => fetchPc()}
            variant="outline"
            className="border-red-600 text-red-600 hover:bg-red-50"
          >
            再試行
          </Button>
          <Link href="/pcs">
            <Button variant="outline" className="">
              PC一覧に戻る
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const isAdmin = session?.user?.role === 'Admin';
  const isOwner = !!session?.user?.id && session.user.id === pc.ownerId;
  const canReturn = pc.status === 'InUse' && (isOwner || isAdmin);

  const basicItems = [
    { label: '管理番号', value: pc.pcId },
    { label: 'オーナー', value: pc.ownerName || '未割り当て' },
    { label: 'PC種別', value: getPcTypeDisplay(pc.type) },
    { label: 'PC名', value: formatSpecValue(pc.pcName) },
    { label: '登録日時', value: formatDateTime(pc.createdAt) },
    { label: '更新日時', value: formatDateTime(pc.updatedAt) },
  ];

  const specItems = [
    { label: 'メーカー', value: formatSpecValue(pc.manufacturer) },
    { label: 'モデル', value: formatSpecValue(pc.model) },
    { label: 'CPU', value: formatSpecValue(pc.cpu) },
    { label: 'メモリ', value: formatSpecValue(pc.memory) },
    { label: 'ストレージ', value: formatSpecValue(pc.storage) },
    { label: 'OS', value: formatSpecValue(pc.os) },
    { label: 'GPU', value: formatSpecValue(pc.gpu) },
    { label: 'シリアル番号', value: formatSpecValue(pc.serialNumber) },
  ];

  return (
    <>
      <ECSLoadingState
        isLoading={ecsLoading.isLoading}
        status={ecsLoading.status}
        remainingSeconds={ecsLoading.remainingSeconds}
      />
      <div className="container mx-auto max-w-4xl p-6 space-y-6">
        <div className="flex flex-wrap justify-between items-center gap-4">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold text-gray-900">PC詳細 - {pc.pcId}</h1>
            <span
              className={`px-3 py-1 inline-flex text-sm leading-5 font-semibold rounded-full ${getStatusColor(
                pc.status,
              )}`}
            >
              {getStatusDisplay(pc.status)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {canReturn && (
              <Link href={`/pcs/${encodeURIComponent(pc.pcId)}/return`}>
                <Button className="bg-amber-600 hover:bg-amber-700 text-white">
                  返却手続きへ
                </Button>
              </Link>
            )}
            <Link href="/pcs">
              <Button variant="outline" className="">
                PC一覧に戻る
              </Button>
            </Link>
          </div>
        </div>

        <Card className="">
          <CardHeader className="">
            <CardTitle className="text-xl">基本情報</CardTitle>
          </CardHeader>
          <CardContent className="">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {basicItems.map((item) => (
                <div key={item.label} className="border-b border-gray-100 pb-2">
                  <dt className="text-xs font-medium text-gray-500">{item.label}</dt>
                  <dd className="mt-1 text-sm font-medium text-gray-900">{item.value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <Card className="">
          <CardHeader className="">
            <CardTitle className="text-xl">スペック情報</CardTitle>
          </CardHeader>
          <CardContent className="">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {specItems.map((item) => (
                <div key={item.label} className="border-b border-gray-100 pb-2">
                  <dt className="text-xs font-medium text-gray-500">{item.label}</dt>
                  <dd className="mt-1 text-sm text-gray-900">{item.value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card className="">
            <CardHeader className="">
              <CardTitle className="text-xl">ステータス更新（管理者専用）</CardTitle>
            </CardHeader>
            <CardContent className="">
              {statusMessage && (
                <div
                  role="alert"
                  className={`p-3 mb-4 rounded text-sm ${
                    statusMessage.type === 'success'
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {statusMessage.text}
                </div>
              )}
              <form onSubmit={handleStatusUpdate} className="space-y-4">
                <div>
                  <Label htmlFor="pcStatusSelect" className="block mb-1">
                    新しいステータス
                  </Label>
                  <select
                    id="pcStatusSelect"
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value as PC['status'])}
                    disabled={isUpdatingStatus}
                    className="flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label} ({opt.value})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label htmlFor="statusReason" className="block mb-1">
                    変更理由（任意）
                  </Label>
                  <Textarea
                    id="statusReason"
                    value={statusReason}
                    onChange={(e) => setStatusReason(e.target.value)}
                    placeholder="例: 故障のため廃棄待ちへ変更"
                    rows={3}
                    disabled={isUpdatingStatus}
                    className=""
                  />
                </div>
                <Button
                  type="submit"
                  disabled={selectedStatus === pc.status || isUpdatingStatus}
                  className=""
                >
                  {isUpdatingStatus ? '更新中...' : 'ステータスを更新'}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  );
}
