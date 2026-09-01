<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import LearningNav from '@/components/LearningNav.vue'
import LearningRecordEditor from '@/components/LearningRecordEditor.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import { formatWorkspaceDate, recordTypeLabels } from '@/domain/workspace'
import { useLearningStore } from '@/stores/learning'
import { useProjectStore } from '@/stores/projects'
import type { LearningRecordCreateInput, LearningRecordResponse } from '@/types/learning'

const learningStore = useLearningStore()
const projectStore = useProjectStore()
const pageNumber = ref(1)
const editingRecord = ref<LearningRecordResponse | null>(null)
const showEditor = ref(false)

async function loadRecords(): Promise<void> {
  await learningStore.fetchRecords({ page: pageNumber.value, pageSize: 20 })
}

async function loadReferences(): Promise<void> {
  await Promise.all([
    learningStore.fetchCourses({ page: 1, pageSize: 100 }),
    learningStore.fetchTasks({ page: 1, pageSize: 100 }),
    projectStore.fetchProjects({ page: 1, pageSize: 100 }),
  ])
}

function openEditor(record: LearningRecordResponse | null = null): void {
  editingRecord.value = record
  showEditor.value = true
}

function closeEditor(): void {
  editingRecord.value = null
  showEditor.value = false
}

async function saveRecord(input: LearningRecordCreateInput): Promise<void> {
  const wasEditing = editingRecord.value !== null
  try {
    await learningStore.saveRecord(input, editingRecord.value?.id)
    closeEditor()
    pageNumber.value = 1
    await loadRecords()
    ElMessage.success(wasEditing ? '学习记录已更新' : '学习记录已保存')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '学习记录保存失败，请重试'))
  }
}

async function removeRecord(record: LearningRecordResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除记录“${record.title}”吗？`, '删除学习记录', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning',
    })
    await learningStore.removeRecord(record.id)
    await loadRecords()
    ElMessage.success('学习记录已删除')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '学习记录删除失败，请重试'))
    }
  }
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadRecords()
}

onMounted(() => {
  void Promise.all([loadRecords(), loadReferences()]).catch(() => undefined)
})
</script>

<template>
  <div class="page-shell workspace-page learning-page">
    <LearningNav />
    <header class="page-header learning-record-header">
      <div><p class="page-kicker">Learning Evidence</p><h1>学习记录</h1><p>记录时长、内容和来源，为后续学习报告保留可靠数据。</p></div>
      <div class="learning-record-total"><NumberRoller :value="learningStore.recordPage.total" /><span>条记录</span><button class="primary-command" type="button" @click="openEditor()">记录学习</button></div>
    </header>

    <section v-if="showEditor" class="workspace-panel workspace-editor learning-editor" aria-label="学习记录编辑器">
      <div class="panel-title-row"><h2>{{ editingRecord ? '编辑学习记录' : '保存学习记录' }}</h2><button class="text-command" type="button" @click="closeEditor">关闭</button></div>
      <LearningRecordEditor :key="editingRecord?.id ?? 'new-record'" :initial-value="editingRecord" :courses="learningStore.coursePage.items" :projects="projectStore.projects" :tasks="learningStore.taskPage.items" :submitting="learningStore.saving" @submit="saveRecord" @cancel="closeEditor" />
    </section>

    <div v-if="learningStore.recordError" class="inline-alert is-error" role="alert"><span>{{ learningStore.recordError }}</span><button type="button" @click="loadRecords">重试</button></div>
    <div v-if="learningStore.loadingRecords" class="workspace-list-loading"><span v-for="index in 5" :key="index" /></div>
    <ol v-else-if="learningStore.recordPage.items.length" class="workspace-record-timeline learning-record-timeline">
      <li v-for="record in learningStore.recordPage.items" :key="record.id">
        <div class="workspace-record-timeline__marker" aria-hidden="true" />
        <time :datetime="record.occurred_at">{{ formatWorkspaceDate(record.occurred_at) }}</time>
        <article>
          <div class="panel-title-row"><div><span class="status-chip">{{ recordTypeLabels[record.record_type] }}</span><h2>{{ record.title }}</h2></div><strong>{{ record.duration_minutes }} 分钟</strong></div>
          <p v-if="record.content">{{ record.content }}</p>
          <footer><span>{{ record.course?.name || record.project?.name || record.task?.name || '个人学习' }}</span><div class="learning-row-actions"><button class="text-command" type="button" @click="openEditor(record)">编辑</button><button class="text-command danger-text-command" type="button" :disabled="learningStore.actionKey === `record:${record.id}`" @click="removeRecord(record)">删除</button></div></footer>
        </article>
      </li>
    </ol>
    <section v-else class="empty-state"><h2>还没有学习记录</h2><p>完成一次学习或任务后，保存真实投入和产出。</p><button class="primary-command" type="button" @click="openEditor()">保存第一条记录</button></section>

    <nav v-if="learningStore.recordPage.total_pages > 1" class="pagination" aria-label="学习记录分页">
      <button type="button" :disabled="pageNumber <= 1 || learningStore.loadingRecords" @click="changePage(pageNumber - 1)">上一页</button><span>第 {{ pageNumber }} / {{ learningStore.recordPage.total_pages }} 页</span><button type="button" :disabled="pageNumber >= learningStore.recordPage.total_pages || learningStore.loadingRecords" @click="changePage(pageNumber + 1)">下一页</button>
    </nav>
  </div>
</template>
