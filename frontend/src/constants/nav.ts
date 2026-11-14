export interface NavItem {
  drawer: string
  path: string
  label: string
  caption: string
  permission: string
}

export const NAV_ITEMS: NavItem[] = [
  { drawer: '01', path: '/cases', label: '案件工作台', caption: '待收件 / 已归档 / 异常', permission: 'cases:read' },
  { drawer: '02', path: '/rules', label: '命名规则与批次', caption: '模板版本 / 归档运行', permission: 'rules:read' },
  { drawer: '03', path: '/pending', label: '待确认队列', caption: '低置信件 / 移交清单', permission: 'pending:read' },
]
