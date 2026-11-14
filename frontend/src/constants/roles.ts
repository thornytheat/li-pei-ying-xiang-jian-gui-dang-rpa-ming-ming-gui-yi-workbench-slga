import type { UserRole } from '../types/user'

/* 与 backend/src/constants/roles.py 一一对应 */
export const ROLES: UserRole[] = ['admin', 'analyst', 'auditor']

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: '受理主管',
  analyst: '受理员',
  auditor: '稽核',
}

export const ROLE_PERMISSION_HINT: Record<UserRole, string> = {
  admin: '命名规则版本、归档批次、移交清单导出、审计日志',
  analyst: '发起归档、处理待确认件、案件改判、移交清单导出',
  auditor: '只读案件与批次，可导出稽核清单，不可改件/发起批次',
}

export function can(permissions: string[] | undefined, action: string): boolean {
  return Boolean(permissions && permissions.includes(action))
}
