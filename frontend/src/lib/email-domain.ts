/**
 * Google アカウントのログイン可否を判定するユーティリティ
 */

export interface GoogleAccountClaims {
  email?: string | null;
  emailVerified?: boolean | null;
  hostedDomain?: string | null;
}

export type LoginRejectionReason = 'email_not_verified' | 'domain_not_allowed';

const normalizeDomain = (domain: string | null | undefined): string =>
  (domain ?? '').trim().toLowerCase();

/**
 * メールアドレスのドメイン部分（最後の @ より後ろ）を小文字で返す
 * @param email - メールアドレス
 * @returns ドメイン部分。@ を含まない場合は空文字
 */
export const getEmailDomain = (email: string | null | undefined): string => {
  const normalizedEmail = (email ?? '').trim();
  const atIndex = normalizedEmail.lastIndexOf('@');
  if (atIndex < 0) {
    return '';
  }
  return normalizeDomain(normalizedEmail.slice(atIndex + 1));
};

/**
 * ログインを拒否する理由を返す
 * @param claims - Google のプロフィール情報（email、email_verified、hd）
 * @param allowedDomain - 許可するドメイン（ALLOWED_EMAIL_DOMAIN）
 * @returns 拒否する理由。許可する場合は null
 */
export const getRejectionReason = (
  claims: GoogleAccountClaims,
  allowedDomain: string
): LoginRejectionReason | null => {
  if (claims.emailVerified !== true) {
    return 'email_not_verified';
  }

  const normalizedAllowedDomain = normalizeDomain(allowedDomain);
  if (!normalizedAllowedDomain) {
    return 'domain_not_allowed';
  }

  const isEmailDomainAllowed = getEmailDomain(claims.email) === normalizedAllowedDomain;
  const isHostedDomainAllowed = normalizeDomain(claims.hostedDomain) === normalizedAllowedDomain;
  if (!isEmailDomainAllowed || !isHostedDomainAllowed) {
    return 'domain_not_allowed';
  }

  return null;
};

/**
 * Google アカウントがログインを許可されるかを判定する
 * email_verified が true、かつメールのドメインと hd がどちらも許可ドメインと完全一致する場合のみ許可する
 * @param claims - Google のプロフィール情報（email、email_verified、hd）
 * @param allowedDomain - 許可するドメイン（ALLOWED_EMAIL_DOMAIN）
 * @returns 許可する場合は true
 */
export const isAllowedGoogleAccount = (
  claims: GoogleAccountClaims,
  allowedDomain: string
): boolean => getRejectionReason(claims, allowedDomain) === null;
