'use client';

import React, { useState } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';

// 型定義 (実際のプロジェクトに合わせて調整が必要な場合があります)
interface ReturnFormData {
  returnReason: string;
  pcStatusAtReturn: string;
}

export default function ReturnPage() {
  const params = useParams();
  // URLパラメータからPC IDを取得
  const pcId = params?.pcId as string;

  const [formData, setFormData] = useState<ReturnFormData>({
    returnReason: '',
    pcStatusAtReturn: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pcId) {
      setMessage({ type: 'error', text: 'PC IDが指定されていません。' });
      return;
    }

    setIsLoading(true);
    setMessage(null);

    try {
      // T034で実装したAPIエンドポイントを呼び出す
      const response = await fetch(`/api/pcs/${pcId}/return`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: 'CURRENT_USER_ID', // 実際には認証情報から取得する
          return_reason: formData.returnReason,
          pc_status_at_return: formData.pcStatusAtReturn,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '返却処理に失敗しました。');
      }

      const data = await response.json();
      setMessage({ type: 'success', text: data.message || '返却処理が正常に完了しました。' });
      // フォームをリセット
      setFormData({ returnReason: '', pcStatusAtReturn: '' });

    } catch (error) {
      console.error('Submission error:', error);
      setMessage({ type: 'error', text: (error as Error).message || 'ネットワークエラーが発生しました。' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container mx-auto py-12 max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>PC返却手続き</CardTitle>
          <p className="text-sm text-muted-foreground">PC ID: <span className="font-semibold">{pcId}</span> の返却手続きを行います。</p>
        </CardHeader>
        <CardContent>
          {message && (
            <div className={`p-3 mb-4 rounded ${message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              {message.text}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 返却理由 */}
            <div>
              <Label htmlFor="returnReason">返却理由 <span className="text-red-500">*</span></Label>
              <Textarea
                id="returnReason"
                name="returnReason"
                placeholder="例: 部署異動に伴う返却、故障のためなど"
                value={formData.returnReason}
                onChange={handleChange}
                required
                rows={4}
              />
            </div>

            {/* PCの状態 */}
            <div>
              <Label htmlFor="pcStatusAtReturn">PCの状態 (返却時) <span className="text-red-500">*</span></Label>
              <select
                id="pcStatusAtReturn"
                name="pcStatusAtReturn"
                value={formData.pcStatusAtReturn}
                onChange={handleChange}
                required
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:placeholder-shown:file:file-word-break cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value="" disabled>状態を選択してください</option>
                <option value="良好">良好 (目立った傷や故障なし)</option>
                <option value="軽微な傷">軽微な傷 (外装に小さな傷など)</option>
                <option value="動作不良">動作不良 (特定の機能に問題あり)</option>
                <option value="その他">その他</option>
              </select>
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? '処理中...' : '返却を確定する'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}