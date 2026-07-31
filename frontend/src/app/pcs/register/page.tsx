'use client';

import React, { useState, useEffect } from 'react';
import TerminalCommand from '@/components/terminal-command';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { getUsers, parseSpecs, registerPC } from '@/services/pc-api';

const PCRegisterPage = () => {
  const { data: session } = useSession();
  const [pcName, setPcName] = useState('');
  const [os, setOs] = useState('');
  const [cpu, setCpu] = useState('');
  const [memory, setMemory] = useState('');
  const [storage, setStorage] = useState('');
  const [gpu, setGpu] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [users, setUsers] = useState<any[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const userList = await getUsers();
        setUsers(userList);
        // デフォルトで最初のユーザーをオーナーとして設定
        if (userList.length > 0 && session?.user && (session.user as any).role === 'Admin') {
          setOwnerId(userList[0].userId);
        }
      } catch (error) {
        console.error('ユーザーリストの取得に失敗しました:', error);
      }
    };
    if (session?.user && (session.user as any).role === 'Admin') {
      fetchUsers();
    }
  }, [session]);

  useEffect(() => {
    if (session?.user) {
      if ((session.user as any).role !== 'Admin') {
        // 一般ユーザーの場合は、自身のユーザーIDをオーナーに設定
        const selfId = (session.user as any).id || (session.user as any).sub || '';
        setOwnerId(selfId);
      }
    }
  }, [session]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ownerId) {
      alert('オーナーユーザーを選択してください。');
      return;
    }
    setIsSubmitting(true);

    try {
      // API呼び出しのロジックを実装
      const specsText = await parseSpecs(terminalCommand);
      const result = await registerPC(ownerId, specsText, 'N');
      
      console.log('登録成功:', result);
      setSubmitSuccess(true);
      // 登録成功後に一覧ページにリダイレクト
      setTimeout(() => {
        router.push('/pcs');
      }, 2000);
    } catch (error) {
      console.error('登録エラー:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 仮のコマンド
  const terminalCommand = `powershell -Command "Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory, BiosSerialNumber, ProcessorName, GPUName | ConvertTo-Json"`;

  return (
    <div className="pc-register-page">
      <h1>PC登録</h1>
      
      <div className="terminal-section">
        <h2>スペック取得コマンド</h2>
        <p>以下のコマンドを実行して、PCのスペック情報を取得してください。</p>
        <TerminalCommand command={terminalCommand} />
      </div>

      <div className="form-section">
        <h2>PC情報入力</h2>
        {submitSuccess ? (
          <div className="success-message">
            <p>PCの登録が完了しました。</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {session?.user && (session.user as any).role === 'Admin' ? (
              <div className="form-group mb-4">
                <label htmlFor="ownerId" className="block text-sm font-semibold mb-2">オーナーユーザー（代理登録先） *</label>
                <select
                  id="ownerId"
                  value={ownerId}
                  onChange={(e) => setOwnerId(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded"
                  required
                >
                  <option value="">ユーザーを選択してください</option>
                  {users.map((user) => (
                    <option key={user.userId} value={user.userId}>
                      {user.name} ({user.email})
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              session?.user && (
                <div className="form-group mb-4">
                  <label className="block text-sm font-semibold mb-2">オーナーユーザー</label>
                  <input
                    type="text"
                    value={`${session.user.name || ''} (${session.user.email || ''})`}
                    className="w-full p-2 border border-gray-300 rounded bg-gray-100 cursor-not-allowed"
                    disabled
                  />
                </div>
              )
            )}

            <div className="form-group">
              <label htmlFor="pcName">PC名 *</label>
              <input
                type="text"
                id="pcName"
                value={pcName}
                onChange={(e) => setPcName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="os">オペレーティングシステム *</label>
              <input
                type="text"
                id="os"
                value={os}
                onChange={(e) => setOs(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="cpu">CPU *</label>
              <input
                type="text"
                id="cpu"
                value={cpu}
                onChange={(e) => setCpu(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="memory">メモリ *</label>
              <input
                type="text"
                id="memory"
                value={memory}
                onChange={(e) => setMemory(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="storage">ストレージ *</label>
              <input
                type="text"
                id="storage"
                value={storage}
                onChange={(e) => setStorage(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="gpu">GPU</label>
              <input
                type="text"
                id="gpu"
                value={gpu}
                onChange={(e) => setGpu(e.target.value)}
              />
            </div>

            <button 
              type="submit" 
              disabled={isSubmitting}
              className="submit-button"
            >
              {isSubmitting ? '登録中...' : 'PCを登録'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default PCRegisterPage;