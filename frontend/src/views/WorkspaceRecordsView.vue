<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import LearningRecordForm from '@/components/LearningRecordForm.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import WorkspaceNav from '@/components/WorkspaceNav.vue'
import { formatWorkspaceDate, recordTypeLabels } from '@/domain/workspace'
import { useProjectStore } from '@/stores/projects'
import { useWorkspaceStore } from '@/stores/workspace'
import type { LearningRecordCreateInput } from '@/types/workspace'

const workspaceStore = useWorkspaceStore()
const projectStore = useProjectStore()
const pageNumber = ref(1)
const showForm = ref(false)

async function loadRecords(): Promise<void> {
  try {
    await workspaceStore.fetchRecords({ page: pageNumber.value, pageSize: 20 })
  } catch {
    // Store 已保存可重试提示。
  }
}

async function createRecord(input: LearningRecordCreateInput): Promise<void> {
  try {
    await workspaceStore.createRecord(input)
    showForm.value = false
    pageNumber.value = 1
    await loadRecords()
    ElMessage.success('学习记录已保存')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '学习记录保存失败，请重试'))
  }
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadRecords()
}

onMounted(() => {
  void loadRecords()
  void projectStore.fetchProjects({ page: 1, pageSize: 100 }).catch(() => undefined)
})
</script>

<template>
  <div class="page-shell workspace-page">
    <WorkspaceNav />
    <header class="page-header">
      <div><p class="page-kicker">Learning Records</p><h1>学习记录</h1><p>保存真实投入，让每一次学习都有迹可循。</p></div>
      <button class="primary-command" type="button" @click="showForm = !showForm">{{ showForm ? '收起表单' : '记录学习' }}</button>
    </header>

    <section v-if="showForm" class="workspace-panel workspace-editor" aria-label="保存学习记录">
      <LearningRecordForm :projects="projectStore.projects" :submitting="workspaceStore.saving" @submit="createRecord" @cancel="showForm = false" />
    </section>

    <div class="workspace-record-summary"><NumberRoller :value="workspaceStore.recordPage.total" /><span>条学习记录</span></div>
    <div v-if="workspaceStore.error" class="inline-alert is-error" role="alert"><span>{{ workspaceStore.error }}</span><button type="button" @click="loadRecords">重试</button></div>
    <div v-if="workspaceStore.loading" class="workspace-list-loading"><span v-for="index in 5" :key="index" /></div>
    <ol v-else-if="workspaceStore.recordPage.items.length" class="workspace-record-timeline">
      <li v-for="record in workspaceStore.recordPage.items" :key="record.id">
        <div class="workspace-record-timeline__marker" aria-hidden="true" />
        <time :datetime="record.occurred_at">{{ formatWorkspaceDate(record.occurred_at) }}</time>
        <article>
          <div class="panel-title-row"><h2>{{ record.title }}</h2><span class="status-chip">{{ recordTypeLabels[record.record_type] }}</span></div>
          <p v-if="record.content">{{ record.content }}</p>
          <footer><span>{{ record.project?.name || '个人学习' }}</span><strong>{{ record.duration_minutes }} 分钟</strong></footer>
        </article>
      </li>
    </ol>
    <section v-else class="empty-state"><h2>还没有学习记录</h2><p>完成一次学习后，记录内容、时长和关联项目。</p><button class="primary-command" type="button" @click="showForm = true">保存第一条记录</button></section>

    <nav v-if="workspaceStore.recordPage.total_pages > 1" class="pagination" aria-label="学习记录分页">
      <button type="button" :disabled="pageNumber <= 1 || workspaceStore.loading" @click="changePage(pageNumber - 1)">上一页</button>
      <span>第 {{ pageNumber }} / {{ workspaceStore.recordPage.total_pages }} 页</span>
      <button type="button" :disabled="pageNumber >= workspaceStore.recordPage.total_pages || workspaceStore.loading" @click="changePage(pageNumber + 1)">下一页</button>
    </nav>
  </div>
</template>
