<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { WORKFLOW_STATUS_LABELS } from '@/domain/workflow'
import { useProjectStore } from '@/stores/projects'
import { useWorkflowStore } from '@/stores/workflows'

const router = useRouter()
const projectStore = useProjectStore()
const workflowStore = useWorkflowStore()
const showCreateForm = ref(false)
const validationError = ref<string | null>(null)
const form = reactive({
  projectId: '',
  name: '',
  description: '',
})

async function load(): Promise<void> {
  await Promise.all([
    projectStore.fetchProjects({ page: 1, pageSize: 100 }),
    workflowStore.fetchWorkflows({ page: 1, pageSize: 50 }),
  ])
  if (!form.projectId && projectStore.projects.length > 0) {
    form.projectId = String(projectStore.projects[0].id)
  }
}

async function create(): Promise<void> {
  const name = form.name.trim()
  if (!form.projectId) {
    validationError.value = '请先选择所属项目'
    return
  }
  if (!name) {
    validationError.value = '请输入工作流名称'
    return
  }
  validationError.value = null
  try {
    const workflow = await workflowStore.createWorkflow({
      project_id: Number(form.projectId),
      name,
      description: form.description.trim() || null,
      status: 'draft',
    })
    ElMessage.success('工作流已创建')
    await router.push({ name: 'workflow-editor', params: { id: workflow.id } })
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '工作流创建失败'))
  }
}

async function remove(workflowId: number, name: string): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除工作流“${name}”吗？节点和连线将一并删除。`, '删除工作流', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await workflowStore.deleteWorkflow(workflowId)
    ElMessage.success('工作流已删除')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '工作流删除失败'))
  }
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

onMounted(() => {
  void load().catch(() => undefined)
})
</script>

<template>
  <section class="page-shell workflows-page">
    <header class="workspace-hero workflow-list-hero">
      <div>
        <h1>Workflow 工作区</h1>
        <p>把项目分析过程整理成可保存、可检查的节点图。</p>
      </div>
      <button class="primary-command" type="button" @click="showCreateForm = !showCreateForm">
        {{ showCreateForm ? '收起' : '新建工作流' }}
      </button>
    </header>

    <form v-if="showCreateForm" class="workflow-create-band" @submit.prevent="create">
      <label class="field">
        所属项目
        <select v-model="form.projectId" :disabled="workflowStore.saving">
          <option value="">选择项目</option>
          <option v-for="project in projectStore.projects" :key="project.id" :value="String(project.id)">
            {{ project.name }}
          </option>
        </select>
      </label>
      <label class="field">
        工作流名称
        <input v-model="form.name" maxlength="120" autocomplete="off" placeholder="例如：课程项目分析流程" />
      </label>
      <label class="field workflow-create-band__description">
        说明
        <input v-model="form.description" maxlength="5000" placeholder="记录这张流程图的目标" />
      </label>
      <button class="primary-command" type="submit" :disabled="workflowStore.saving || projectStore.projects.length === 0">
        {{ workflowStore.saving ? '创建中…' : '创建并编辑' }}
      </button>
      <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
      <p v-if="projectStore.projects.length === 0" class="field-error">请先在项目库创建项目。</p>
    </form>

    <div v-if="workflowStore.listError" class="state-panel state-panel--error">
      <strong>工作流加载失败</strong>
      <p>{{ workflowStore.listError }}</p>
      <button class="secondary-command" type="button" @click="load">重试</button>
    </div>

    <div v-else-if="workflowStore.listLoading" class="workflow-list-skeleton" aria-label="工作流加载中">
      <span v-for="index in 3" :key="index" />
    </div>

    <div v-else-if="workflowStore.page.items.length === 0" class="state-panel">
      <strong>还没有工作流</strong>
      <p>从一个项目和一张空画布开始。</p>
      <button class="primary-command" type="button" @click="showCreateForm = true">新建工作流</button>
    </div>

    <div v-else class="workflow-list-board">
      <article v-for="workflow in workflowStore.page.items" :key="workflow.id">
        <div class="workflow-list-board__status">
          <span :class="`status-chip status-${workflow.status}`">{{ WORKFLOW_STATUS_LABELS[workflow.status] }}</span>
          <small>v{{ workflow.version }}</small>
        </div>
        <div>
          <h2>{{ workflow.name }}</h2>
          <p>{{ workflow.description || '暂无说明' }}</p>
          <small>{{ workflow.project.name }} · 更新于 {{ formatDate(workflow.updated_at) }}</small>
        </div>
        <div class="workflow-list-board__metrics">
          <strong>{{ workflow.node_count }}</strong><span>节点</span>
          <strong>{{ workflow.edge_count }}</strong><span>连线</span>
        </div>
        <div class="workflow-list-board__actions">
          <RouterLink class="primary-command" :to="`/workflows/${workflow.id}`">打开编辑器</RouterLink>
          <button
            class="danger-command"
            type="button"
            :disabled="workflowStore.actionKey === `workflow:${workflow.id}`"
            @click="remove(workflow.id, workflow.name)"
          >
            删除
          </button>
        </div>
      </article>
    </div>
  </section>
</template>
