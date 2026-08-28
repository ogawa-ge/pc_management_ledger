'use client';

import React, { useState, useEffect } from 'react';
import TerminalCommand from '@/components/terminal-command';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { getUsers, parseSpecs, registerPC, PcSpecsError } from '@/services/pc-api';

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
  const [users, setUsers] = useState<any[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const router = useRouter();

  // 貼り付け入力欄（ユビキタス言語: 「貼り付け入力欄」）とAI自動抽出まわりの状態
  const [terminalOutput, setTerminalOutput] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionError, setExtractionError] = useState<string | null>(null);
  const [requiredFieldWarning, setRequiredFieldWarning] = useState<string | null>(null);

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
      setMemory(result.memory != null ? String(result.memory) : '');
      setStorage(result.storage != null ? String(result.storage) : '');
      setOs(result.os != null ? String(result.os) : '');
      setManufacturer(result.manufacturer != null ? String(result.manufacturer) : '');
      setModel(result.model != null ? String(result.model) : '');
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

    // FR-009: 重要項目（モデル名）が未入力の場合は警告するが、登録はブロックしない
    setRequiredFieldWarning(model.trim() ? null : 'モデル名が未入力です。可能であれば入力してください。');

    setIsSubmitting(true);

    try {
      // FR-005: 自動反映後に手動で編集された値も含め、現在のフォームstateから登録データを構築する
      const result = await registerPC(
        ownerId,
        { cpu, memory, storage, os, manufacturer, model },
        'N'
      );

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
              disabled={isSubmitting}
              aria-busy={isSubmitting}
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
