/**
 * ロールベースのアクセス制御 (RBAC) ユーティリティ
 * ユーザーの権限に応じて、画面や機能へのアクセスを制御する
 */

// ユーザーのロールを定義
export type UserRole = 'user' | 'admin';

// ユーザー情報のインターフェース
export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}

// アクセス制御のためのロール定義
export const ROLES = {
  USER: 'user',
  ADMIN: 'admin'
} as const;

// アクセス制御のための権限定義
export const PERMISSIONS = {
  VIEW_PCS: 'view_pcs',
  REGISTER_PC: 'register_pc',
  MANAGE_PCS: 'manage_pcs',
  VIEW_USERS: 'view_users',
  MANAGE_USERS: 'manage_users',
  RETURN_PC: 'return_pc'
} as const;

// 各ロールに割り当てられる権限のマッピング
export const ROLE_PERMISSIONS: Record<UserRole, string[]> = {
  [ROLES.USER]: [
    PERMISSIONS.VIEW_PCS,
    PERMISSIONS.REGISTER_PC,
    PERMISSIONS.RETURN_PC
  ],
  [ROLES.ADMIN]: [
    PERMISSIONS.VIEW_PCS,
    PERMISSIONS.REGISTER_PC,
    PERMISSIONS.MANAGE_PCS,
    PERMISSIONS.VIEW_USERS,
    PERMISSIONS.MANAGE_USERS,
    PERMISSIONS.RETURN_PC
  ]
};

/**
 * ユーザーが特定の権限を持っているかを確認する
 * @param user - ユーザー情報
 * @param permission - 確認する権限
 * @returns ユーザーが権限を持っている場合はtrue、そうでない場合はfalse
 */
export function hasPermission(user: User | null, permission: string): boolean {
  if (!user || !user.role) {
    return false;
  }
  
  const userPermissions = ROLE_PERMISSIONS[user.role];
  return userPermissions.includes(permission);
}

/**
 * ユーザーが特定のロールを持っているかを確認する
 * @param user - ユーザー情報
 * @param role - 確認するロール
 * @returns ユーザーがロールを持っている場合はtrue、そうでない場合はfalse
 */
export function hasRole(user: User | null, role: UserRole): boolean {
  if (!user || !user.role) {
    return false;
  }
  
  return user.role === role;
}