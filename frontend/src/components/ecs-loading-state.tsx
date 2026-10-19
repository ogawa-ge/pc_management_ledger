'use client';

import React, { useState, useEffect } from 'react';
import './ecs-loading-state.css';

interface ECSLoadingStateProps {
  /**
   * ローディングが表示されるかどうか
   */
  isLoading: boolean;
  /**
   * カスタムメッセージ（デフォルト: "ECS起動中..."）
   */
  message?: string;
  /**
   * フェードアウトのアニメーション時間（ミリ秒）
   */
  fadeOutDuration?: number;
  /**
   * バックグラウンドの透明度（0-1）
   */
  backdropOpacity?: number;
  status?: 'starting' | 'processing' | 'timeout';
  remainingSeconds?: number;
  onCancel?: () => void;
  onRetry?: () => void;
}

/**
 * ECS コールドスタート時のローディング UI コンポーネント
 *
 * ECS タスクの起動に時間がかかる場合、このコンポーネントを使用して
 * ユーザーに対して適切なローディング表示を行い、待機時間をハンドリングします。
 */
export const ECSLoadingState: React.FC<ECSLoadingStateProps> = ({
  isLoading,
  message = 'ECS起動中...',
  fadeOutDuration = 300,
  backdropOpacity = 0.7,
  status = 'starting',
  remainingSeconds,
  onCancel,
  onRetry,
}) => {
  const [shouldRender, setShouldRender] = useState(isLoading);
  const [isVisible, setIsVisible] = useState(isLoading);

  useEffect(() => {
    if (isLoading) {
      setShouldRender(true);
      // アニメーションを再トリガーするため、わずかな遅延後に表示
      const timer = setTimeout(() => setIsVisible(true), 10);
      return () => clearTimeout(timer);
    } else {
      // フェードアウトアニメーション
      setIsVisible(false);
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, fadeOutDuration);
      return () => clearTimeout(timer);
    }
  }, [isLoading, fadeOutDuration]);

  if (!shouldRender) {
    return null;
  }

  return (
    <div
      className={`ecs-loading-overlay ${isVisible ? 'visible' : ''}`}
      style={{ '--backdrop-opacity': backdropOpacity } as React.CSSProperties}
    >
      <div className="ecs-loading-container">
        {/* スピナー */}
        <div className="ecs-spinner">
          <div className="spinner-circle"></div>
          <div className="spinner-circle"></div>
          <div className="spinner-circle"></div>
        </div>

        {/* メッセージ */}
        <p className="ecs-loading-message">
          {status === 'timeout' ? 'バックエンドを起動できませんでした' : message}
        </p>

        {/* サブテキスト */}
        <p className="ecs-loading-submessage">
          {status === 'timeout'
            ? '操作は完了していません。安全に再試行できます。'
            : status === 'processing'
              ? '同じ操作を処理中です。完了まで自動的に再試行します。'
              : '初回アクセス時は起動に数十秒から数分かかる場合があります'}
        </p>
        {status !== 'timeout' && remainingSeconds !== undefined && (
          <p className="ecs-loading-countdown">自動待機の残り: {remainingSeconds}秒</p>
        )}

        {/* プログレスバー */}
        <div className="ecs-progress-bar">
          <div className="progress-fill"></div>
        </div>
        <div className="ecs-loading-actions">
          {status === 'timeout' && onRetry && <button onClick={onRetry}>再試行</button>}
          {status !== 'timeout' && onCancel && <button onClick={onCancel}>キャンセル</button>}
        </div>
      </div>
    </div>
  );
};

/**
 * ECS ローディング状態フック
 *
 * ECS 起動プロセスのローディング状態を管理するカスタムフック
 */
export const useECSLoadingState = (initialState: boolean = false) => {
  const [isLoading, setIsLoading] = useState(initialState);
  const [status, setStatus] = useState<'starting' | 'processing' | 'timeout'>('starting');
  const [remainingSeconds, setRemainingSeconds] = useState(180);

  const startLoading = () => setIsLoading(true);
  const stopLoading = () => setIsLoading(false);

  return {
    isLoading,
    setIsLoading,
    startLoading,
    stopLoading,
    status,
    setStatus,
    remainingSeconds,
    setRemainingSeconds,
  };
};

export default ECSLoadingState;
