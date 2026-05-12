'use client';

import React, { useState } from 'react';

interface TerminalCommandProps {
  command: string;
}

const TerminalCommand: React.FC<TerminalCommandProps> = ({ command }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="terminal-command">
      <div className="terminal-header">
        <span className="terminal-title">ターミナルコマンド</span>
        <button 
          onClick={handleCopy}
          className="copy-button"
        >
          {copied ? 'コピー完了!' : 'クリップボードにコピー'}
        </button>
      </div>
      <pre className="terminal-output">
        <code>{command}</code>
      </pre>
    </div>
  );
};

export default TerminalCommand;