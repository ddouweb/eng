<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  if (!form.username || !form.password) {
    message.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  const r = await auth.login(form.username, form.password)
  loading.value = false
  if (r.code === 200) {
    message.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } else {
    message.error(r.message || '用户名或密码错误')
  }
}
</script>

<template>
  <div class="login-wrap">
    <NCard title="📚 家庭英语学习" class="login-card">
      <NForm @keyup.enter="submit">
        <NFormItem label="用户名">
          <NInput v-model:value="form.username" placeholder="admin" />
        </NFormItem>
        <NFormItem label="密码">
          <NInput v-model:value="form.password" type="password" placeholder="admin123" />
        </NFormItem>
        <NButton type="primary" block :loading="loading" @click="submit">登录</NButton>
      </NForm>
    </NCard>
  </div>
</template>

<style scoped>
.login-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
}
.login-card {
  width: 360px;
}
</style>
