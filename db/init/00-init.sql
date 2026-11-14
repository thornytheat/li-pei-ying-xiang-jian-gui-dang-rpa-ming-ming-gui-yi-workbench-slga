-- 只要容器首次初始化会执行；业务表由 backend entrypoint 的 bootstrap_db 建。
-- 这里只确保 schema 存在，避免不同初始化顺序下的权限告警。
CREATE SCHEMA IF NOT EXISTS docflow;
