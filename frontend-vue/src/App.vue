<script setup lang="ts">
import { computed, h } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
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

// 侧栏：除登录外的全部路由，按 meta.icon + title 渲染 RouterLink。
const menuOptions = computed<MenuOption[]>(() =>
  router
    .getRoutes()
    .filter((r) => !r.meta?.public && r.name)
    .map((r) => ({
      label: () =>
        h(
          RouterLink,
          { to: r.path },
          { default: () => `${r.meta?.icon ?? ''} ${r.meta?.title ?? String(r.name)}` },
        ),
      key: r.path,
    })),
)

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
          <NLayoutSider bordered :width="220" content-style="padding: 14px;">
            <div class="brand">📚 家庭英语</div>
            <NMenu :options="menuOptions" :value="route.path" />
            <div class="logout">
              <NButton block secondary @click="logout">🚪 退出登录</NButton>
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
}
.logout {
  margin-top: 16px;
}
</style>
