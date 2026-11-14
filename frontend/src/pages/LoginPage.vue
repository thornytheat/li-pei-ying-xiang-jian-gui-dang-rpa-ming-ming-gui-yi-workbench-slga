<template>
  <div class="login">
    <section class="room">
      <header class="room__head">
        <span class="room__plate mono">理赔档案室 · A-03</span>
        <span class="room__date mono">{{ stamp }}</span>
      </header>

      <div class="room__body">
        <p class="tiny">恒安保险经纪 · 理赔受理组（14 人 · 日均 200+ 件）</p>
        <h1 class="room__title">
          影像件归档 RPA<br />
          与命名归一工作台
        </h1>
        <p class="room__lead">
          共享盘与邮箱的扫描件、手机翻拍、PDF 混在一个文件夹里。受理员手工改名、肉眼分类型，
          重名覆盖后连原片都追不回来。这里把「扫描 → 识别 → 命名 → 复核 → 移交」缩成一条可复核的流水。
        </p>

        <ul class="drawers">
          <li v-for="item in NAV_ITEMS" :key="item.path">
            <span class="drawers__no mono">{{ item.drawer }}</span>
            <span class="drawers__label">{{ item.label }}</span>
            <span class="drawers__caption">{{ item.caption }}</span>
          </li>
        </ul>

        <div class="room__stats">
          <div>
            <span class="mono">210</span>
            <em>件待归档影像</em>
          </div>
          <div>
            <span class="mono">60</span>
            <em>在办案件</em>
          </div>
          <div>
            <span class="mono">09</span>
            <em>重复投递件</em>
          </div>
        </div>
      </div>

      <div class="room__foot">
        <SealMark text="影像件归档" tone="red" />
        <SealMark text="稽核抽查" tone="blue" size="sm" />
        <p class="tiny">
          原片只读 · 只对副本改名落盘<br />重复判据为内容 SHA-256，不靠文件名
        </p>
      </div>
    </section>

    <section class="desk">
      <div class="desk__slip slip slip-in">
        <div class="desk__head">
          <p class="tiny tiny--caps">借阅登记 · READER SLIP</p>
          <h2>登录受理台</h2>
          <p class="desk__sub">
            用受理组邮箱登录。角色决定能开哪个抽屉：主管改规则、受理员跑批次、稽核只看不改。
          </p>
        </div>

        <form class="desk__form" @submit.prevent="onSubmit">
          <div class="field field--ruled">
            <label for="email">邮箱</label>
            <input id="email" v-model.trim="email" type="email" autocomplete="username" placeholder="analyst@docflow.io" required />
          </div>
          <div class="field field--ruled">
            <label for="password">口令</label>
            <input
              id="password"
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="Demo@2026"
              required
            />
          </div>

          <ErrorNotice v-if="auth.error" :message="auth.error" :retry-label="''" />

          <button class="btn btn--seal desk__submit" type="submit" :disabled="auth.loading">
            {{ auth.loading ? '登记中…' : '登记并进入档案室' }}
          </button>
        </form>

        <div class="desk__accounts">
          <p class="tiny">演示账号（口令统一 Demo@2026）</p>
          <button
            v-for="account in accounts"
            :key="account.email"
            type="button"
            class="account"
            @click="fill(account.email)"
          >
            <span class="account__role">{{ account.role }}</span>
            <span class="account__mail mono">{{ account.email }}</span>
            <span class="account__hint">{{ account.hint }}</span>
          </button>
        </div>

        <p class="desk__note tiny">
          登录会写一条 audit_logs；同一 IP 一分钟内超过 12 次失败会被限流拦下。
        </p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import SealMark from '../components/common/SealMark.vue'
import { NAV_ITEMS } from '../constants/nav'
import { useAuthStore } from '../stores/authStore'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('Demo@2026')
const accounts = [
  { role: '受理主管', email: 'admin@docflow.io', hint: '改规则 / 跑批次 / 看审计' },
  { role: '受理员', email: 'analyst@docflow.io', hint: '跑批次 / 处理待确认件' },
  { role: '稽核', email: 'auditor@docflow.io', hint: '只读 + 导出稽核清单' },
]

const stamp = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
}).format(new Date())

function fill(value: string) {
  email.value = value
  password.value = 'Demo@2026'
}

async function onSubmit() {
  try {
    await auth.login(email.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/cases'
    router.replace(redirect)
  } catch {
    /* 错误信息由 store / ErrorNotice 呈现 */
  }
}
</script>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
}

/* ------------------------------------------------------------ 左侧档案室 ---- */
.room {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 34px 48px 30px;
  border-right: 2px solid var(--ink);
  background:
    linear-gradient(180deg, oklch(91% 0.028 84), oklch(87% 0.032 80) 78%, oklch(84% 0.036 79));
  overflow: hidden;
}

.room::before {
  content: '';
  position: absolute;
  right: -140px;
  bottom: -180px;
  width: 520px;
  height: 520px;
  border: 1px solid oklch(52% 0.05 64 / 0.35);
  border-radius: 50%;
  pointer-events: none;
}

.room::after {
  content: '';
  position: absolute;
  right: 40px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: oklch(52% 0.05 64 / 0.25);
}

.room__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1px solid var(--line-strong);
  padding-bottom: 10px;
}

.room__plate {
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  color: var(--kraft-deep);
}

.room__date {
  font-size: 0.74rem;
  color: var(--ink-3);
}

.room__body {
  padding: 28px 0 20px;
  max-width: 600px;
}

.room__title {
  margin-top: 10px;
  font-size: var(--step-4);
  line-height: 1.16;
  letter-spacing: 0.01em;
}

.room__lead {
  margin-top: 16px;
  color: var(--ink-2);
  max-width: 46ch;
}

.drawers {
  list-style: none;
  padding: 0;
  margin: 24px 0 0;
  border-top: 1px solid var(--line-strong);
}

.drawers li {
  display: grid;
  grid-template-columns: 34px minmax(0, 9.5em) minmax(0, 1fr);
  gap: 12px;
  align-items: baseline;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}

.drawers__no {
  color: var(--kraft-deep);
  font-size: 0.8rem;
}

.drawers__label {
  font-weight: 500;
}

.drawers__caption {
  font-size: 0.74rem;
  color: var(--ink-3);
  letter-spacing: 0.03em;
}

.room__stats {
  display: flex;
  gap: 34px;
  margin-top: 24px;
  padding-top: 14px;
  border-top: 2px solid var(--ink);
}

.room__stats div {
  display: flex;
  flex-direction: column;
}

.room__stats span {
  font-size: clamp(1.7rem, 1.2rem + 1.6vw, 2.5rem);
  line-height: 1;
  letter-spacing: -0.02em;
}

.room__stats em {
  font-style: normal;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  color: var(--ink-3);
  margin-top: 6px;
}

.room__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 20px;
}

.room__foot p {
  color: var(--ink-3);
  line-height: 1.6;
}

/* -------------------------------------------------------------- 右侧登记台 ---- */
.desk {
  display: grid;
  place-items: center;
  padding: 40px 6vw;
  background:
    radial-gradient(40rem 24rem at 110% 0%, oklch(90% 0.03 88 / 0.8), transparent 70%),
    oklch(94% 0.016 86);
}

.desk__slip {
  width: min(430px, 100%);
  padding: 30px 28px 24px;
}

.desk__head h2 {
  margin-top: 4px;
}

.desk__sub {
  margin-top: 8px;
  font-size: var(--step--1);
  color: var(--ink-2);
}

.desk__form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin: 24px 0 22px;
}

.desk__submit {
  margin-top: 4px;
  width: 100%;
  padding: 11px 18px;
  letter-spacing: 0.14em;
}

.desk__accounts {
  border-top: 1px dashed var(--line-strong);
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.account {
  display: grid;
  grid-template-columns: 5.2em minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 0 10px;
  text-align: left;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--line);
  padding: 7px 2px;
  cursor: pointer;
  transition: background 140ms ease;
}

.account:hover {
  background: var(--paper-2);
}

.account__role {
  grid-row: 1 / 3;
  align-self: center;
  font-size: var(--step--1);
  color: var(--seal-blue);
  letter-spacing: 0.06em;
}

.account__mail {
  font-size: 0.78rem;
}

.account__hint {
  font-size: 0.68rem;
  color: var(--ink-3);
}

.desk__note {
  margin-top: 16px;
  text-transform: none;
  letter-spacing: 0.01em;
  line-height: 1.6;
}

@media (max-width: 1080px) {
  .login {
    grid-template-columns: minmax(0, 1fr);
  }
  .room {
    border-right: none;
    border-bottom: 2px solid var(--ink);
    padding: 26px 26px 22px;
  }
  .room__body {
    padding: 24px 0 18px;
  }
  .room__title {
    font-size: var(--step-3);
  }
  .room__foot {
    padding-top: 18px;
  }
  .desk {
    padding: 30px 20px 40px;
  }
}

@media (max-width: 767px) {
  .room {
    padding: 20px 16px 18px;
  }
  .drawers li {
    grid-template-columns: 26px minmax(0, 1fr);
  }
  .drawers__caption {
    display: none;
  }
  .room__stats {
    gap: 20px;
  }
}
</style>
