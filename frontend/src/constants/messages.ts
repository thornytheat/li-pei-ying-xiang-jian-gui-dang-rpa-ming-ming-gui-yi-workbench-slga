export const ERROR_MESSAGES: Record<string, string> = {
  AUTH_REQUIRED: '请先登录',
  AUTH_INVALID: '登录状态无效，请重新登录',
  TOKEN_EXPIRED: '登录已过期，请重新登录',
  FORBIDDEN: '当前角色无权执行该操作',
  NOT_FOUND: '对象不存在',
  VALIDATION_ERROR: '请求参数不合法',
  CASE_NOT_FOUND: '案件不存在',
  ATTACHMENT_NOT_FOUND: '附件不存在',
  ATTACHMENT_NOT_PENDING: '该附件不在待确认状态',
  POLICY_NO_INVALID: '保单号格式应为 P + 12 位数字',
  TEMPLATE_INVALID: '命名模板缺少必需占位符',
  RULE_VERSION_CONFLICT: '规则版本已变更，请刷新后重试',
  RUN_NOT_READY: '批次尚未生成完成',
  RUN_BUSY: '已有批次正在执行，请稍后再发起',
  RUN_FAILED: '批次执行失败，请查看批次日志',
  RATE_LIMITED: '请求过于频繁，请稍后重试',
  INTERNAL_ERROR: '服务内部错误',
}

export const EMPTY_HINTS = {
  cases: '这个抽屉还是空的。先去「命名规则与归档批次」发起一次归档，扫描完成后案件会落到对应的抽屉里。',
  search: '没有匹配的案件。清空搜索词，或换成保单号后 6 位再试。',
  pending: '待确认队列已清空。低置信件都处理完了，可以导出一份移交清单收工。',
  runs: '还没有批次。先跑一次「试运行」看清 210 件会落到哪些名字，再正式归档。',
  rules: '规则库是空的，先创建 v1 模板。',
} as const
