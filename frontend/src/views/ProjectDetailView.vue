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
import { useCommunityStore } from '@/stores/community'
import type { ProjectCreateInput } from '@/types/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const communityStore = useCommunityStore()
const editMode = ref(route.query.edit === '1')
const submitError = ref<string | null>(null)
const publicationOpen = ref(false)
const publicationTags = ref('')
const publicationError = ref<string | null>(null)

const projectId = computed(() => {
  const value = Number(route.params.id)
  return Number.isInteger(value) && value > 0 ? value : null
})
const project = computed(() => projectStore.currentProject)
const stack = computed(() => (project.value ? getProjectStack(project.value) : []))

async function loadProject(): Promise<void> {
  if (projectId.value === null) return
  try {
    const result = await projectStore.fetchProject(projectId.value)
    publicationTags.value = result.tags.map((tag) => tag.name).join('，')
  } catch {
    // Store 已保存可重试的用户提示。
  }
}

function parsePublicationTags(): string[] | null {
  const tags = publicationTags.value
    .split(/[,，\n]/)
    .map((tag) => tag.trim())
    .filter((tag, index, values) => tag && values.findIndex((value) => value.toLowerCase() === tag.toLowerCase()) === index)
  if (tags.length > 5) {
    publicationError.value = '最多添加 5 个标签'
    return null
  }
  if (tags.some((tag) => tag.length > 50)) {
    publicationError.value = '每个标签不能超过 50 个字符'
    return null
  }
  return tags
}

async function publishProject(): Promise<void> {
  if (projectId.value === null) return
  publicationError.value = null
  const tags = parsePublicationTags()
  if (tags === null) return
  try {
    await communityStore.publishProject(projectId.value, tags)
    await loadProject()
    publicationOpen.value = false
    ElMessage.success('项目已发布到校园社区')
  } catch (error: unknown) {
    publicationError.value = getApiErrorMessage(error, '项目发布失败，请重试')
  }
}

async function unpublishProject(): Promise<void> {
  if (!project.value) return
  try {
    await ElMessageBox.confirm('撤下后，社区中的项目详情和互动入口将不可访问。', '确认撤下项目', {
      confirmButtonText: '撤下',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await communityStore.unpublishProject(project.value.id)
    await loadProject()
    ElMessage.success('项目已从社区撤下')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '项目撤下失败，请重试'))
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
          <RouterLink
            v-if="project.is_published"
            class="primary-command"
            :to="`/community/projects/${project.id}`"
          >
            查看社区页
          </RouterLink>
          <button
            v-if="project.is_published"
            class="secondary-command"
            type="button"
            :disabled="communityStore.actionLoading"
            @click="unpublishProject"
          >
            撤下社区
          </button>
          <button
            v-else
            class="primary-command"
            type="button"
            @click="publicationOpen = !publicationOpen"
          >
            {{ publicationOpen ? '收起发布设置' : '发布到社区' }}
          </button>
          <button class="secondary-command" type="button" @click="editMode = !editMode">
            {{ editMode ? '退出编辑' : '编辑项目' }}
          </button>
          <button class="danger-command" type="button" :disabled="projectStore.saving" @click="removeProject">
            删除项目
          </button>
        </div>
      </header>

      <section v-if="publicationOpen && !project.is_published" class="publication-panel" aria-labelledby="publication-title">
        <div class="panel-title-row">
          <h2 id="publication-title">发布到校园代码社区</h2>
          <span>项目说明和技术栈将对登录用户可见</span>
        </div>
        <label class="field">
          <span>项目标签</span>
          <input v-model="publicationTags" maxlength="254" placeholder="例如：Vue，校园服务，课程设计" />
          <small>使用逗号分隔，最多 5 个标签</small>
        </label>
        <div v-if="publicationError" class="inline-alert is-error" role="alert">{{ publicationError }}</div>
        <div class="form-actions">
          <button class="secondary-command" type="button" :disabled="communityStore.actionLoading" @click="publicationOpen = false">取消</button>
          <button class="primary-command" type="button" :disabled="communityStore.actionLoading" @click="publishProject">
            {{ communityStore.actionLoading ? '正在发布…' : '确认发布' }}
          </button>
        </div>
      </section>

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
          <div v-if="project.tags.length" class="tag-row" aria-label="社区标签">
            <span v-for="tag in project.tags" :key="tag.id" class="tech-tag">{{ tag.name }}</span>
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
