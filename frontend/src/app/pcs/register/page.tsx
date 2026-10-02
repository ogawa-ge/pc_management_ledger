'use client';

import React, { useState, useEffect, useCallback } from 'react';
import TerminalCommand from '@/components/terminal-command';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { ApiError, getUsers, parseSpecs, registerPC, PcSpecsError } from '@/services/pc-api';
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
  const [manufacturer, setManufacturer] = useState('');
  const [model, setModel] = useState('');
  const [gpu, setGpu] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [userListStatus, setUserListStatus] = useState<UserListStatus>('idle');
  const [userListError, setUserListError] = useState<string | null>(null);
  const [registrationError, setRegistrationError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const router = useRouter();

  // 貼り付け入力欄（ユビキタス言語: 「貼り付け入力欄」）とAI自動抽出まわりの状態
  const [terminalOutput, setTerminalOutput] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [requiredFieldWarning, setRequiredFieldWarning] = useState<string | null>(null);

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

  // 貼り付けられたターミナル出力をGemini APIで抽出し、フォームに自動反映する（US1, FR-002〜FR-004, FR-006〜FR-008）
  const handleExtract = async () => {
    setExtractionError(null);

    if (!terminalOutput.trim()) {
      setExtractionError('貼り付け欄が空です。ターミナルの実行結果を貼り付けてください。');
      return;
    }

    // FR-006: 送信前にJSONとして解析できるか検証し、不正な場合はAPIを呼ばずエラー表示する
    try {
      JSON.parse(terminalOutput);
    } catch {
      setExtractionError('貼り付けた内容がJSONとして解析できません。正しい形式で貼り付けてください。');
      return;
    }

    setIsExtracting(true);
    try {
      const result = await parseSpecs(terminalOutput);

      if ('error' in result) {
        const errorResult = result as PcSpecsError;
        // FR-007: 3回リトライしても失敗した場合はエラー内容を表示し手動入力を促す。貼り付け内容はクリアしない。
        setExtractionError(
          errorResult.retriesExhausted
            ? `AIによる自動抽出に失敗しました（${errorResult.error}）。3回再試行しましたが失敗したため、以下のフォームに手動で入力してください。`
            : `AIによる自動抽出に失敗しました（${errorResult.error}）。`
        );
        return;
      }

      // FR-004: 判断可能な項目のみをフォームへ反映する（取得できなかった項目は空欄のまま）
      setCpu(result.cpu != null ? String(result.cpu) : '');
      // メモリ・ストレージはGB・小数点第1位までの表示に統一する（AIの推論結果の精度までは求めない）
      setMemory(result.memory != null && !Number.isNaN(Number(result.memory)) ? Number(result.memory).toFixed(1) : '');
      setStorage(result.storage != null && !Number.isNaN(Number(result.storage)) ? Number(result.storage).toFixed(1) : '');
      setOs(result.os != null ? String(result.os) : '');
      setManufacturer(result.manufacturer != null ? String(result.manufacturer) : '');
      setModel(result.model != null ? String(result.model) : '');
      setGpu(result.gpu != null ? String(result.gpu) : '');
      setPcName(result.pcName != null ? String(result.pcName) : '');
    } catch (error) {
      console.error('スペック抽出エラー:', error);
      setExtractionError('AIによる自動抽出中に通信エラーが発生しました。手動で入力してください。');
    } finally {
      setIsExtracting(false);
    }
  };

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

    // FR-009: 重要項目（モデル名）が未入力の場合は警告するが、登録はブロックしない
    setRequiredFieldWarning(model.trim() ? null : 'モデル名が未入力です。可能であれば入力してください。');

    setIsSubmitting(true);
    setRegistrationError(null);

    try {
      // FR-005: 自動反映後に手動で編集された値も含め、現在のフォームstateから登録データを構築する
      const result = await registerPC(
        ownerId,
        { cpu, memory, storage, os, manufacturer, model, gpu, pcName },
        'N',
        session?.user?.id
      );

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

  // Get-ComputerInfoの実プロパティ名は要求仕様の項目名と異なる
  // (TotalPhysicalMemory→CsTotalPhysicalMemory、ProcessorName→CsProcessors配下のName、
  //  GPUNameはGet-ComputerInfoに存在せずWin32_VideoControllerが必要)ため、
  // 出力キー名は仕様通りに保ちつつ実プロパティから値を詰め替える。
  // BIOSシリアル番号はGet-ComputerInfoのプロパティ名がPowerShellのバージョンにより
  // BiosSerialNumber/BiosSeralNumber(スペルミス)で揺れるため、バージョン非依存のWin32_BIOSから取得する。
  // メーカー・モデル・PC名はGet-ComputerInfoのCsManufacturer/CsModel/CsNameから取得。
  // ストレージ総容量はGet-ComputerInfoに存在しないため、Win32_DiskDriveの合計サイズ(バイト値)を取得し、
  // メモリ容量と同様にGBへの変換はGemini側のプロンプト指示（AIの推論）に委ねる。
  // WindowsProductName（Get-ComputerInfoの値）はレジストリのProductName文字列をそのまま返すが、
  // Windows 11でも"Windows 10 ..."のままになっているOS側の既知の不具合がある。
  // 代わりにWin32_OperatingSystemのCaptionを使うと、実機のバージョンに応じた正しい値
  // （例: "Microsoft Windows 11 Pro"）が取得できるため、こちらを取得元とする。
  const terminalCommand = `$info = Get-ComputerInfo; $osCaption = (Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption); $gpu = (Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name); $bios = (Get-CimInstance Win32_BIOS | Select-Object -ExpandProperty SerialNumber); $storageBytes = (Get-CimInstance Win32_DiskDrive | Measure-Object -Property Size -Sum).Sum; [PSCustomObject]@{WindowsProductName=$osCaption; WindowsVersion=$info.WindowsVersion; TotalPhysicalMemory=$info.CsTotalPhysicalMemory; BiosSerialNumber=$bios; ProcessorName=($info.CsProcessors | Select-Object -First 1 -ExpandProperty Name); GPUName=$gpu; Manufacturer=$info.CsManufacturer; Model=$info.CsModel; PCName=$info.CsName; StorageTotalBytes=$storageBytes} | ConvertTo-Json`;

  return (
    <div className="pc-register-page">
      <h1>PC登録</h1>

      <div className="terminal-section">
        <h2>スペック取得コマンド</h2>
        <p>以下のコマンドをPowerShell(コマンドプロンプトではなくPowerShell)に貼り付けて実行し、PCのスペック情報を取得してください。</p>
        <TerminalCommand command={terminalCommand} />

        <div className="form-group mt-4">
          <label htmlFor="terminalOutput" className="block text-sm font-semibold mb-2">
            ターミナル実行結果を貼り付けてください
          </label>
          <textarea
            id="terminalOutput"
            value={terminalOutput}
            onChange={(e) => setTerminalOutput(e.target.value)}
            rows={6}
            className="w-full p-2 border border-gray-300 rounded font-mono text-sm"
            placeholder="ここにコマンドの実行結果（JSON）を貼り付けてください"
          />
          <button
            type="button"
            onClick={handleExtract}
            disabled={isExtracting}
            aria-busy={isExtracting}
            className="extract-button mt-2"
          >
            {isExtracting ? '抽出中...' : 'スペックを抽出'}
          </button>
          {extractionError && (
            <p role="alert" aria-live="polite" className="error-message mt-2">
              {extractionError}
            </p>
          )}
        </div>
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
              <label htmlFor="memory">メモリ (GB) *</label>
              <input
                type="text"
                id="memory"
                value={memory}
                onChange={(e) => setMemory(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="storage">ストレージ (GB) *</label>
              <input
                type="text"
                id="storage"
                value={storage}
                onChange={(e) => setStorage(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="manufacturer">メーカー</label>
              <input
                type="text"
                id="manufacturer"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="model">モデル</label>
              <input
                type="text"
                id="model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
              {requiredFieldWarning && (
                <p role="alert" aria-live="polite" className="warning-message">
                  {requiredFieldWarning}
                </p>
              )}
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
