'use client';

import React, { useState } from 'react';
import TerminalCommand from '@/components/terminal-command';
import { useRouter } from 'next/navigation';

const PCRegisterPage = () => {
  const [pcName, setPcName] = useState('');
  const [os, setOs] = useState('');
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
        if (userList.length > 0) {
          setOwnerId(userList[0].id);
        }
      } catch (error) {
        console.error('ユーザーリストの取得に失敗しました:', error);
      }
    };
    fetchUsers();
  }, []);

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