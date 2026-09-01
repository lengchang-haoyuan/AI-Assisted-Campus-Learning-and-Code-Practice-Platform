<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { getProjectCover } from '@/assets/projectCovers'
import ProjectForm from '@/components/ProjectForm.vue'
import {
  difficultyLabels,
  formatProjectTime,
  formatRequirement,
  getProjectStack,
  statusLabels,
} from '@/domain/projects'
import { useProjectStore } from '@/stores/projects'
import type { ProjectCreateInput } from '@/types/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const editMode = ref(route.query.edit === '1')
const submitError = ref<string | null>(null)

const projectId = computed(() => {
  const value = Number(route.params.id)
  return Number.isInteger(value) && value > 0 ? value : null
})
const project = computed(() => projectStore.currentProject)
const stack = computed(() => (project.value ? getProjectStack(project.value) : []))

async function loadProject(): Promise<void> {
  if (projectId.value === null) return
  try {
    await projectStore.fetchProject(projectId.value)
  } catch {
    // Store 已保存可重试的用户提示。
  }
}

async function updateProject(input: ProjectCreateInput): Promise<void> {
  if (projectId.value === null) return
  submitError.value = null
  try {
    await projectStore.updateProject(projectId.value, input)
    editMode.value = false
    ElMessage.success('项目已更新')
  } catch (error: unknown) {
    submitError.value = getApiErrorMessage(error, '项目更新失败，请检查输入后重试')
  }
}

async function removeProject(): Promise<void> {
  if (!project.value) return
  try {
    await ElMessageBox.confirm(`删除“${project.value.name}”后无法恢复。`, '确认删除项目', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
    await projectStore.deleteProject(project.value.id)
    ElMessage.success('项目已删除')
    await router.replace({ name: 'projects' })
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除失败，请重试'))
  }
}

onMounted(() => {
  void loadProject()
})

onBeforeUnmount(() => {
  projectStore.clearCurrentProject()
})
</script>

<template>
  <div class="page-shell project-detail-page">
    <RouterLink class="back-link" to="/projects">返回项目库</RouterLink>

    <div v-if="projectId === null" class="inline-alert is-error" role="alert">项目地址无效。</div>

    <div v-else-if="projectStore.detailLoading" class="detail-skeleton" aria-label="项目加载中">
      <span /><span /><span />
    </div>

    <div v-else-if="projectStore.detailError" class="inline-alert is-error" role="alert">
      <span>{{ projectStore.detailError }}</span>
      <button type="button" @click="loadProject">重试</button>
    </div>

    <template v-else-if="project">
      <header class="project-detail-header">
        <div>
          <div class="tag-row">
            <span class="status-chip" :data-status="project.status">{{ statusLabels[project.status] }}</span>
            <span class="tech-tag">{{ difficultyLabels[project.difficulty] }}</span>
          </div>
          <h1>{{ project.name }}</h1>
          <p>{{ project.description || '这个项目还没有补充说明。' }}</p>
        </div>
        <div class="detail-actions">
          <button class="secondary-command" type="button" @click="editMode = !editMode">
            {{ editMode ? '退出编辑' : '编辑项目' }}
          </button>
          <button class="danger-command" type="button" :disabled="projectStore.saving" @click="removeProject">
            删除项目
          </button>
        </div>
      </header>

      <section v-if="editMode" class="editor-panel" aria-labelledby="edit-project-title">
        <h2 id="edit-project-title">编辑项目信息</h2>
        <div v-if="submitError" class="inline-alert is-error" role="alert">{{ submitError }}</div>
        <ProjectForm
          :initial-value="project"
          :submitting="projectStore.saving"
          submit-label="保存修改"
          @submit="updateProject"
          @cancel="editMode = false"
        />
      </section>

      <div v-else class="project-detail-grid">
        <section class="project-overview">
          <img :src="getProjectCover(project.id)" :alt="`${project.name} 项目封面`" />
          <div class="code-preview" aria-label="项目配置摘要">
            <span>project = {</span>
            <span>&nbsp;&nbsp;name: "{{ project.name }}",</span>
            <span>&nbsp;&nbsp;status: "{{ project.status }}",</span>
            <span>&nbsp;&nbsp;owner: "{{ project.owner.username }}"</span>
            <span>}</span>
          </div>
        </section>

        <section class="detail-section">
          <h2>技术栈</h2>
          <div class="tag-row">
            <span v-for="technology in stack" :key="technology" class="tech-tag">{{ technology }}</span>
            <span v-if="stack.length === 0" class="tech-tag is-muted">暂未设置</span>
          </div>
          <dl class="detail-facts">
            <div><dt>主要语言</dt><dd>{{ project.language || '未设置' }}</dd></div>
            <div><dt>核心框架</dt><dd>{{ project.framework || '未设置' }}</dd></div>
            <div><dt>创建时间</dt><dd>{{ formatProjectTime(project.created_at) }}</dd></div>
            <div><dt>更新时间</dt><dd>{{ formatProjectTime(project.updated_at) }}</dd></div>
          </dl>
        </section>

        <section class="detail-section">
          <h2>项目需求</h2>
          <ul v-if="project.requirements?.length" class="requirement-list">
            <li v-for="(requirement, index) in project.requirements" :key="index">
              {{ formatRequirement(requirement) }}
            </li>
          </ul>
          <p v-else class="muted-copy">暂未填写项目需求。</p>
        </section>

        <section class="detail-section">
          <h2>交付要求</h2>
          <p class="long-copy">{{ project.output_requirement || '暂未填写交付要求。' }}</p>
        </section>
      </div>
    </template>
  </div>
</template>
