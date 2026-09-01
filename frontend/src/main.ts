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
    void router.replace({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})

app.mount('#app')
