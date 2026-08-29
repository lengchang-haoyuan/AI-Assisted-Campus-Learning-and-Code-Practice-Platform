<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'

import { useHealthStore } from '@/stores/health'

const healthStore = useHealthStore()

const statusLabel = computed(() => {
  if (healthStore.loading) return '检测中'
  if (healthStore.error) return '连接失败'
  if (healthStore.data?.status === 'ok') return '运行正常'
  return '尚未检测'
})

const statusType = computed<'success' | 'danger' | 'info' | 'warning'>(() => {
  if (healthStore.loading) return 'warning'
  if (healthStore.error) return 'danger'
  if (healthStore.data?.status === 'ok') return 'success'
  return 'info'
})

onMounted(() => {
  void healthStore.fetchHealth()
})

onBeforeUnmount(() => {
  healthStore.cancel()
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div>
        <p class="brand">ScholarHub</p>
        <p class="product-name">AI 辅助校园学习与代码实践平台</p>
      </div>
      <el-tag :type="statusType" effect="plain">{{ statusLabel }}</el-tag>
    </header>

    <main class="workspace">
      <section class="intro" aria-labelledby="page-title">
        <p class="eyebrow">P00 · 工程初始化</p>
        <h1 id="page-title">前后端服务状态</h1>
        <p class="intro-copy">
          当前页面通过 Axios 调用 FastAPI 健康检查接口，用于验证 ScholarHub 的基础通信链路。
        </p>
      </section>

      <section class="status-panel" aria-live="polite" :aria-busy="healthStore.loading">
        <div class="panel-heading">
          <div>
            <p class="panel-label">API CONNECTION</p>
            <h2>后端健康检查</h2>
          </div>
          <el-button :loading="healthStore.loading" @click="healthStore.fetchHealth">
            重新检测
          </el-button>
        </div>

        <div v-if="healthStore.loading" class="state-block">
          <el-skeleton :rows="3" animated />
        </div>

        <el-alert
          v-else-if="healthStore.error"
          :title="healthStore.error"
          type="error"
          :closable="false"
          show-icon
        />

        <el-descriptions v-else-if="healthStore.data" :column="1" border>
          <el-descriptions-item label="服务状态">
            <el-tag type="success">{{ healthStore.data.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="服务名称">
            {{ healthStore.data.service }}
          </el-descriptions-item>
          <el-descriptions-item label="API 版本">
            {{ healthStore.data.version }}
          </el-descriptions-item>
        </el-descriptions>

        <el-empty v-else description="尚未获取服务状态" />
      </section>

      <section class="request-path" aria-label="请求调用链">
        <span>Vue 页面</span>
        <span aria-hidden="true">→</span>
        <span>Pinia</span>
        <span aria-hidden="true">→</span>
        <span>Axios</span>
        <span aria-hidden="true">→</span>
        <span>FastAPI</span>
      </section>
    </main>
  </div>
</template>
