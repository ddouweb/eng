<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  useMessage,
  type FormInst,
  type FormRules,
} from 'naive-ui'

import { useAuthStore } from '@/stores/auth'

// 仅本地开发测试用：默认账号 admin / admin123。不要在 UI 中预填或提示。
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const message = useMessage()

const formRef = ref<FormInst | null>(null)
const form = reactive({ username: '', password: '' })
const loading = ref(false)

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: ['input', 'blur'] }],
  password: [{ required: true, message: '请输入密码', trigger: ['input', 'blur'] }],
}

async function submit() {
  // 提交前先做行内校验，未通过则不发起请求
  try {
    await formRef.value?.validate()
  } catch {
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
      <NForm ref="formRef" :model="form" :rules="rules" @keyup.enter="submit">
        <NFormItem label="用户名" path="username">
          <NInput v-model:value="form.username" placeholder="请输入用户名" />
        </NFormItem>
        <NFormItem label="密码" path="password">
          <NInput v-model:value="form.password" type="password" placeholder="请输入密码" />
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
