import { createApp } from 'vue'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'

import App from './App.vue'
import { setUnauthorizedHandler } from './auth/session'
import router from './router'
import { useAuthStore } from './stores/auth'
import { pinia } from './stores'
import './styles/main.css'

const app = createApp(App)

app.use(pinia).use(router)

const authStore = useAuthStore(pinia)
setUnauthorizedHandler(() => {
  authStore.clearSession()
  if (router.currentRoute.value.meta.requiresAuth) {
    // 完整导航销毁所有 Store 和旧会话请求，避免切换账号后显示旧数据。
    window.location.replace(router.resolve({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    }).href)
  }
})

app.mount('#app')
