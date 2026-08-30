import { createPinia } from 'pinia'
import { createApp } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDescriptions,
  ElDescriptionsItem,
  ElEmpty,
  ElSkeleton,
  ElTag,
} from 'element-plus'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-alert.css'
import 'element-plus/theme-chalk/el-button.css'
import 'element-plus/theme-chalk/el-descriptions.css'
import 'element-plus/theme-chalk/el-empty.css'
import 'element-plus/theme-chalk/el-skeleton.css'
import 'element-plus/theme-chalk/el-tag.css'

import App from './App.vue'
import { setUnauthorizedHandler } from './auth/session'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.component('ElAlert', ElAlert)
app.component('ElButton', ElButton)
app.component('ElDescriptions', ElDescriptions)
app.component('ElDescriptionsItem', ElDescriptionsItem)
app.component('ElEmpty', ElEmpty)
app.component('ElSkeleton', ElSkeleton)
app.component('ElTag', ElTag)

app.use(pinia).use(router)

const authStore = useAuthStore(pinia)
setUnauthorizedHandler(() => authStore.clearSession())
void authStore.restoreSession()

app.mount('#app')
