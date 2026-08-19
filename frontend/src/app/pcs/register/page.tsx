'use client';

import React, { useState, useEffect, useCallback } from 'react';
import TerminalCommand from '@/components/terminal-command';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { ApiError, getUsers, parseSpecs, registerPC } from '@/services/pc-api';
import { User } from '@/types/user';

const getUserLabel = (user: User): string => {
  if (user.name && user.email) return `${user.name} (${user.email})`;
  if (user.name) return `${user.name} (${user.userId})`;
  if (user.email) return `${user.email} (${user.userId})`;
  return user.userId;
};

type UserListStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

const PCRegisterPage = () => {
  const { data: session } = useSession();
  const [pcName, setPcName] = useState('');
  const [os, setOs] = useState('');
  const [cpu, setCpu] = useState('');
  const [memory, setMemory] = useState('');
  const [storage, setStorage] = useState('');
  const [gpu, setGpu] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [userListStatus, setUserListStatus] = useState<UserListStatus>('idle');
  const [userListError, setUserListError] = useState<string | null>(null);
  const [registrationError, setRegistrationError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const router = useRouter();

  const fetchUsers = useCallback(async () => {
    if (!session?.user?.id || session.user.role !== 'Admin') return;

    setUserListStatus('loading');
    setUserListError(null);
    setUsers([]);
    setOwnerId('');
    try {
      const userList = await getUsers(session.user.id);
      setUsers(userList);
      setUserListStatus(userList.length === 0 ? 'empty' : 'success');
    } catch (error) {
      console.error('ユーザーリストの取得に失敗しました:', error);
      setUserListError('ユーザー一覧を取得できませんでした。時間をおいて再試行してください。');
      setUserListStatus('error');
    }
  }, [session?.user?.id, session?.user?.role]);

  useEffect(() => {
    if (session?.user?.role === 'Admin' && session.user.id) {
      fetchUsers();
    }
  }, [fetchUsers, session?.user?.id, session?.user?.role]);

  useEffect(() => {
    if (session?.user) {
      if (session.user.role !== 'Admin') {
        // 一般ユーザーの場合は、自身のユーザーIDをオーナーに設定
        setOwnerId(session.user.id || '');
      }
    }
  }, [session]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ownerId) {
      alert('オーナーユーザーを選択してください。');
      return;
    }
    if (session?.user?.role === 'Admin' && !users.some((user) => user.userId === ownerId)) {
      setRegistrationError('有効なオーナーユーザーを選択してください。');
      return;
    }
    setIsSubmitting(true);
    setRegistrationError(null);

    try {
      // API呼び出しのロジックを実装
      const specsText = await parseSpecs(terminalCommand);
      const result = await registerPC(ownerId, specsText, 'N', session?.user?.id);
      
      console.log('登録成功:', result);
      setSubmitSuccess(true);
      // 登録成功後に一覧ページにリダイレクト
      setTimeout(() => {
        router.push('/pcs');
      }, 2000);
    } catch (error) {
      console.error('登録エラー:', error);
      if (error instanceof ApiError && error.status === 404) {
        setOwnerId('');
        setRegistrationError('選択したオーナーユーザーは利用できなくなりました。候補を再取得して選択し直してください。');
        setUserListStatus('error');
        setUserListError('オーナー候補が変更されています。再試行して最新の一覧を取得してください。');
      } else {
        setRegistrationError(error instanceof Error ? error.message : 'PCの登録に失敗しました。');
      }
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
            {session?.user?.role === 'Admin' ? (
              <div className="form-group mb-4">
                <label htmlFor="ownerId" className="block text-sm font-semibold mb-2">オーナーユーザー（代理登録先） *</label>
                <select
                  id="ownerId"
                  value={ownerId}
                  onChange={(e) => setOwnerId(e.target.value)}
                  className="w-full p-2 border border-gray-300 rounded"
                  disabled={userListStatus !== 'success' || isSubmitting}
                  required
                >
                  <option value="">
                    {userListStatus === 'loading' ? 'ユーザーを取得中です...' : 'ユーザーを選択してください'}
                  </option>
                  {users.map((user) => (
                    <option key={user.userId} value={user.userId}>
                      {getUserLabel(user)}
                    </option>
                  ))}
                </select>
                {userListStatus === 'loading' && (
                  <p role="status" className="mt-2 text-gray-600">ユーザー一覧を取得中です...</p>
                )}
                {userListStatus === 'empty' && (
                  <p role="status" className="mt-2 text-gray-600">登録済みユーザーがいません。</p>
                )}
                {userListStatus === 'error' && (
                  <div role="alert" className="mt-2 text-red-600">
                    <p>{userListError}</p>
                    <button
                      type="button"
                      onClick={fetchUsers}
                      disabled={isSubmitting}
                      className="mt-2 border border-red-600 rounded px-3 py-1"
                    >
                      再試行
                    </button>
                  </div>
                )}
              </div>
            ) : (
              session?.user && (
                <div className="form-group mb-4">
                  <label className="block text-sm font-semibold mb-2">オーナーユーザー</label>
                  <input
                    type="text"
                    value={session.user.name && session.user.email
                      ? `${session.user.name} (${session.user.email})`
                      : session.user.name || session.user.email || session.user.id}
                    className="w-full p-2 border border-gray-300 rounded bg-gray-100 cursor-not-allowed"
                    disabled
                  />
                </div>
              )
            )}

            {registrationError && (
              <p role="alert" className="mb-4 text-red-600">{registrationError}</p>
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
              disabled={isSubmitting || (session?.user?.role === 'Admin' && (userListStatus !== 'success' || !users.some((user) => user.userId === ownerId)))}
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