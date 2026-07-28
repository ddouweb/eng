<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import type { RouteRecordNormalized } from 'vue-router'
import {
  NButton,
  NConfigProvider,
  NDialogProvider,
  NLayout,
  NLayoutContent,
  NLayoutSider,
  NMenu,
  NMessageProvider,
  dateZhCN,
  zhCN,
  type MenuOption,
} from 'naive-ui'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLogin = computed(() => route.name === 'login')

// 窄屏侧栏折叠：本版本 NLayoutSider 无 breakpoint prop，故用 matchMedia 自行驱动 collapsed。
// <768px 自动折叠到 collapsed-width(64px)，保证 375-414px 手机端侧栏不再挤占 >50% 屏宽；
// 桌面端保持 220px 展开，用户可点 trigger 手动折叠。
const collapsed = ref(false)
let mql: MediaQueryList | null = null
function applyMq(matches: boolean): void {
  collapsed.value = matches
}
function onMqChange(e: MediaQueryListEvent): void {
  applyMq(e.matches)
}
onMounted(() => {
  mql = window.matchMedia('(max-width: 767px)')
  applyMq(mql.matches)
  mql.addEventListener('change', onMqChange)
})
onBeforeUnmount(() => {
  mql?.removeEventListener('change', onMqChange)
  mql = null
})

// 业务分组：11 项导航按 首页/练习/管理/数据/AI 分组，提升可读性。
type MenuGroupDef = { label: string; names: string[] }
const GROUPS: MenuGroupDef[] = [
  { label: '首页', names: ['dashboard'] },
  { label: '练习', names: ['practice', 'wrong-book'] },
  { label: '管理', names: ['units', 'words', 'plans', 'search'] },
  { label: '数据', names: ['stats', 'progress', 'weekly-settlement'] },
  { label: 'AI', names: ['ai'] },
]

const routeByName = computed(() => {
  const m = new Map<string, RouteRecordNormalized>()
  for (const r of router.getRoutes()) {
    if (r.name) m.set(String(r.name), r)
  }
  return m
})

// 侧栏菜单：按业务分组渲染；emoji 作 icon（折叠态仅显图标），label 仅显标题。
const menuOptions = computed<MenuOption[]>(() => {
  const rmap = routeByName.value
  return GROUPS.map((g) => ({
    type: 'group' as const,
    label: g.label,
    key: `group-${g.label}`,
    children: g.names
      .map((n) => rmap.get(n))
      .filter((r): r is RouteRecordNormalized => !!r && !r.meta?.public)
      .map<MenuOption>((r) => {
        const icon = r.meta?.icon
        return {
          label: () =>
            h(
              RouterLink,
              { to: r.path },
              { default: () => r.meta?.title ?? String(r.name) },
            ),
          key: String(r.name),
          icon: icon ? () => h('span', String(icon)) : undefined,
        }
      }),
  }))
})

// 选中态：按 route.matched 取最深 name 作键（非字面 path），避免 query/params 变化导致高亮错位。
const activeKey = computed(() => {
  const matched = route.matched
  for (let i = matched.length - 1; i >= 0; i--) {
    if (matched[i].name) return String(matched[i].name)
  }
  return ''
})

// 折叠态收紧内边距，给 NMenu collapsed 图标留位（64 - 8*2 = 48 = NMenu collapsed-width）。
const siderContentStyle = computed(() => (collapsed.value ? 'padding: 8px;' : 'padding: 14px;'))

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN">
    <NMessageProvider>
      <NDialogProvider>
        <RouterView v-if="isLogin" />
        <NLayout v-else has-sider style="height: 100vh">
          <NLayoutSider
            bordered
            :width="220"
            :collapsed-width="64"
            :collapsed="collapsed"
            collapse-mode="width"
            show-trigger
            :content-style="siderContentStyle"
            @update:collapsed="collapsed = $event"
          >
            <div class="brand">
              <span class="brand-icon" aria-hidden="true">📚</span>
              <span v-if="!collapsed" class="brand-text">家庭英语</span>
            </div>
            <NMenu
              :options="menuOptions"
              :value="activeKey"
              :collapsed="collapsed"
              :collapsed-width="48"
              :collapsed-icon-size="20"
            />
            <div class="logout">
              <NButton block secondary aria-label="退出登录" @click="logout">
                <template v-if="collapsed">🚪</template>
                <template v-else>🚪 退出登录</template>
              </NButton>
            </div>
          </NLayoutSider>
          <NLayoutContent content-style="padding: 22px; overflow: auto;">
            <RouterView />
          </NLayoutContent>
        </NLayout>
      </NDialogProvider>
    </NMessageProvider>
  </NConfigProvider>
</template>

<style scoped>
.brand {
  font-weight: 700;
  font-size: 16px;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  overflow: hidden;
}
.brand-icon {
  flex-shrink: 0;
}
.logout {
  margin-top: 16px;
}
</style>
