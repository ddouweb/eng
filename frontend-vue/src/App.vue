<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import type { RouteRecordNormalized } from 'vue-router'
import {
  NButton,
  NConfigProvider,
  NDialogProvider,
  NDrawer,
  NDrawerContent,
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
import { STAT_THEME_OVERRIDES } from '@/constants/ui'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const isLogin = computed(() => route.name === 'login')

// 响应式布局：≥768px 桌面持久侧栏（可手动折叠）；<768px 改汉堡抽屉，侧栏不占位→内容全屏。
const isMobile = ref(false)
const collapsed = ref(false) // 桌面端手动折叠
const drawerOpen = ref(false) // 移动端抽屉开关
let mql: MediaQueryList | null = null
function applyMq(matches: boolean): void {
  isMobile.value = matches
  if (matches) drawerOpen.value = false // 切到移动端时收起抽屉
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
// 路由变化后收起移动端抽屉（点菜单跳转即关）
watch(
  () => route.path,
  () => {
    if (isMobile.value) drawerOpen.value = false
  },
)

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
// 移动端：顶部固定栏留位（48px）+ 左右收紧到 16px，给内容更多横向空间。
const contentStyle = computed(() =>
  isMobile.value ? 'padding: 56px 16px 22px; overflow: auto;' : 'padding: 22px; overflow: auto;',
)

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="STAT_THEME_OVERRIDES">
    <NMessageProvider>
      <NDialogProvider>
        <RouterView v-if="isLogin" />
        <NLayout v-else has-sider style="height: 100vh">
          <!-- 桌面：持久侧栏，可手动折叠 -->
          <NLayoutSider
            v-if="!isMobile"
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
              <span v-if="!collapsed" class="brand-text">英语学习</span>
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

          <!-- 移动端：汉堡抽屉（侧栏不占位 → 内容全屏） -->
          <NDrawer v-if="isMobile" v-model:show="drawerOpen" :width="240" placement="left">
            <NDrawerContent body-content-style="padding: 14px;">
              <div class="brand">
                <span class="brand-icon" aria-hidden="true">📚</span>
                <span class="brand-text">英语学习</span>
              </div>
              <NMenu :options="menuOptions" :value="activeKey" />
              <div class="logout">
                <NButton block secondary @click="logout">🚪 退出登录</NButton>
              </div>
            </NDrawerContent>
          </NDrawer>

          <NLayoutContent :content-style="contentStyle">
            <!-- 移动端顶部固定栏：汉堡 + 标题 -->
            <div v-if="isMobile" class="mobile-bar">
              <NButton quaternary circle aria-label="打开菜单" @click="drawerOpen = true">
                ☰
              </NButton>
              <span class="mobile-title">📚 英语学习</span>
            </div>
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
/* 移动端顶部固定栏 */
.mobile-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: #fff;
  border-bottom: 1px solid #e6e8eb;
  z-index: 100;
}
.mobile-title {
  font-weight: 700;
  font-size: 15px;
}
</style>
