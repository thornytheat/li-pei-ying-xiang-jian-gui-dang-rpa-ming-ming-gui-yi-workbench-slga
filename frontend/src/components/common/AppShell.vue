<template>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <span class="brand__tab mono">DF</span>
        <div class="brand__text">
          <strong class="brand__name">docflow</strong>
          <span class="tiny">理赔影像件归档 RPA</span>
        </div>
      </div>

      <div class="rail__org">
        <span class="tiny">委托方</span>
        <p>恒安保险经纪<br />理赔受理组 · 14 人</p>
      </div>

      <nav class="drawers" aria-label="抽屉导航">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="drawer"
          :class="{ 'drawer--active': isActive(item.path) }"
        >
          <span class="drawer__no mono">{{ item.drawer }}</span>
          <span class="drawer__text">
            <strong>{{ item.label }}</strong>
            <em>{{ item.caption }}</em>
          </span>
        </router-link>
      </nav>

      <div class="rail__foot">
        <SealMark text="归档专用章" size="sm" tone="red" />
        <div>
          <p class="tiny">只动副本</p>
          <p class="rail__foot-note">原片只读，重命名与落盘都走归档卷</p>
        </div>
      </div>
    </aside>

    <div class="stage">
      <header class="topstrip">
        <div class="topstrip__left">
          <span class="tiny">{{ today }}</span>
          <span class="topstrip__sep">/</span>
          <span class="tiny">受理组分机 8021</span>
          <span class="topstrip__sep">/</span>
          <span class="tiny">归档卷 {{ health ? health.archive_files : '—' }} 件</span>
        </div>
        <div class="topstrip__right">
          <span class="health-dot" :class="healthClass" aria-hidden="true"></span>
          <span class="tiny">{{ healthLabel }}</span>
          <span class="topstrip__sep">/</span>
          <span class="who">
            <strong>{{ auth.displayName || auth.email || '未登录' }}</strong>
            <span class="tag tag--seal">{{ roleLabel }}</span>
          </span>
          <button type="button" class="btn btn--ghost btn--small" @click="logout">退出</button>
        </div>
      </header>

      <main class="stage__body">
        <slot />
      </main>

      <footer class="stage__foot tiny">
        docflow · 恒安保险经纪理赔受理组 · 重名不覆盖：内容 SHA-256 相同判重复、不落盘
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchHealth, type HealthPayload } from '../../api/health'
import { NAV_ITEMS } from '../../constants/nav'
import { ROLE_LABELS } from '../../constants/roles'
import { useAuthStore } from '../../stores/authStore'
import SealMark from './SealMark.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const health = ref<HealthPayload | null>(null)

const navItems = computed(() => NAV_ITEMS.filter((item) => auth.can(item.permission)))
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
const today = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  weekday: 'short',
}).format(new Date())

const healthLabel = computed(() => {
  if (!health.value) return '状态读取中'
  if (health.value.status === 'ok') return '库与缓存正常'
  return health.value.database ? '缓存异常' : '数据库异常'
})

const healthClass = computed(() => {
  if (!health.value) return 'is-wait'
  return health.value.status === 'ok' ? 'is-ok' : 'is-bad'
})

function isActive(path: string): boolean {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  try {
    health.value = await fetchHealth()
  } catch {
    health.value = null
  }
})
</script>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 246px minmax(0, 1fr);
  min-height: 100vh;
}

/* ------------------------------------------------------------------ 左轨 ---- */
.rail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 26px 18px 22px;
  border-right: 2px solid var(--ink);
  background:
    linear-gradient(180deg, oklch(90% 0.03 82), oklch(87% 0.032 80));
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand__tab {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 2px solid var(--ink);
  background: var(--kraft);
  color: var(--paper-3);
  font-size: 0.98rem;
  letter-spacing: 0.06em;
  border-radius: 3px 12px 3px 3px;
}

.brand__text {
  display: flex;
  flex-direction: column;
}

.brand__name {
  font-family: var(--font-mono);
  font-size: 1.12rem;
  letter-spacing: 0.06em;
}

.rail__org {
  border-top: 1px solid var(--line-strong);
  border-bottom: 1px solid var(--line-strong);
  padding: 10px 0;
}

.rail__org p {
  font-size: var(--step--1);
  color: var(--ink-2);
  line-height: 1.5;
}

.drawers {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.drawer {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 10px 10px 8px;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  color: var(--ink-2);
  border-bottom: none;
  transition: background 160ms ease, border-color 160ms ease, transform 160ms cubic-bezier(0.22, 1, 0.36, 1);
}

.drawer:hover {
  background: oklch(92% 0.025 84 / 0.8);
  transform: translateX(2px);
}

.drawer--active {
  background: var(--paper-3);
  border-color: var(--line-strong);
  border-left: 3px solid var(--seal-red);
  color: var(--ink);
}

.drawer__no {
  font-size: 0.78rem;
  color: var(--kraft-deep);
  padding-top: 1px;
}

.drawer__text {
  display: flex;
  flex-direction: column;
  line-height: 1.35;
}

.drawer__text strong {
  font-weight: 500;
  font-size: var(--step-0);
}

.drawer__text em {
  font-style: normal;
  font-size: 0.68rem;
  color: var(--ink-3);
  letter-spacing: 0.04em;
}

.rail__foot {
  margin-top: auto;
  display: flex;
  gap: 12px;
  align-items: center;
  border-top: 1px dashed var(--line-strong);
  padding-top: 14px;
}

.rail__foot-note {
  font-size: 0.68rem;
  color: var(--ink-3);
  line-height: 1.4;
  max-width: 15ch;
}

/* ------------------------------------------------------------------ 主区 ---- */
.stage {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topstrip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 28px;
  border-bottom: 1px solid var(--line-strong);
  background: oklch(93% 0.02 84 / 0.75);
  backdrop-filter: none;
  flex-wrap: wrap;
}

.topstrip__left,
.topstrip__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.topstrip__sep {
  color: var(--line-strong);
}

.who {
  display: flex;
  align-items: center;
  gap: 8px;
}

.who strong {
  font-weight: 500;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1px solid var(--ink);
  background: var(--line-strong);
}

.health-dot.is-ok {
  background: var(--seal-green);
}
.health-dot.is-bad {
  background: var(--seal-red);
}
.health-dot.is-wait {
  background: var(--warn);
}

.stage__body {
  flex: 1;
  padding: 26px 28px 34px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1560px;
  width: 100%;
}

.stage__foot {
  padding: 14px 28px 22px;
  color: var(--ink-3);
  border-top: 1px solid var(--line);
  text-transform: none;
  letter-spacing: 0.02em;
}

@media (max-width: 1100px) {
  .shell {
    grid-template-columns: minmax(0, 1fr);
  }
  .rail {
    position: static;
    height: auto;
    flex-direction: row;
    align-items: center;
    gap: 14px;
    overflow-x: auto;
    padding: 12px 16px;
    border-right: none;
    border-bottom: 2px solid var(--ink);
  }
  .rail__org,
  .rail__foot {
    display: none;
  }
  .drawers {
    flex-direction: row;
  }
  .drawer {
    border-bottom: 1px solid transparent;
    border-left: none;
    border-top: 3px solid transparent;
    white-space: nowrap;
  }
  .drawer--active {
    border-left: none;
    border-top: 3px solid var(--seal-red);
  }
  .drawer__text em {
    display: none;
  }
  .topstrip {
    padding: 10px 18px;
  }
  .stage__body {
    padding: 20px 18px 26px;
  }
}

@media (max-width: 767px) {
  .rail {
    flex-wrap: wrap;
  }
  .drawer__no {
    display: none;
  }
  .stage__body {
    padding: 16px 14px 24px;
    gap: 16px;
  }
  .stage__foot {
    padding: 12px 14px 18px;
  }
  .topstrip__left {
    display: none;
  }
}
</style>
