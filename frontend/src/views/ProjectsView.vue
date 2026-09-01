<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { getProjectCover } from '@/assets/projectCovers'
import ProjectFlipCard from '@/components/ProjectFlipCard.vue'
import ProjectForm from '@/components/ProjectForm.vue'
import { useProjectStore } from '@/stores/projects'
import type { ProjectCreateInput, ProjectResponse } from '@/types/project'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const pageNumber = ref(1)
const editorOpen = ref(false)
const submitError = ref<string | null>(null)

const searchQuery = computed(() =>
  typeof route.query.q === 'string' ? route.query.q.trim().toLowerCase() : '',
)
const visibleProjects = computed(() => {
  if (!searchQuery.value) return projectStore.projects
  return projectStore.projects.filter((project) => {
    const searchText = [
      project.name,
      project.description,
      project.language,
      project.framework,
      project.frontend,
      project.backend,
      project.database,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return searchText.includes(searchQuery.value)
  })
})

async function loadProjects(): Promise<void> {
  try {
    await projectStore.fetchProjects({ page: pageNumber.value, pageSize: 12 })
  } catch {
    // Store 已保存可重试的用户提示。
  }
}

async function createProject(input: ProjectCreateInput): Promise<void> {
  submitError.value = null
  try {
    const project = await projectStore.createProject(input)
    ElMessage.success('项目已创建')
    editorOpen.value = false
    await router.push({ name: 'project-detail', params: { id: project.id } })
  } catch (error: unknown) {
    submitError.value = getApiErrorMessage(error, '项目创建失败，请检查输入后重试')
  }
}

function editProject(project: ProjectResponse): void {
  void router.push({ name: 'project-detail', params: { id: project.id }, query: { edit: '1' } })
}

async function removeProject(project: ProjectResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除“${project.name}”后无法恢复。`, '确认删除项目', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
    await projectStore.deleteProject(project.id)
    ElMessage.success('项目已删除')
    if (projectStore.projects.length === 0 && pageNumber.value > 1) {
      pageNumber.value -= 1
      await loadProjects()
    }
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除失败，请重试'))
  }
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadProjects()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <div class="page-shell projects-page">
    <header class="page-header">
      <div>
        <h1>项目库</h1>
        <p>管理项目范围、技术栈、状态和交付目标。</p>
      </div>
      <button class="primary-command" type="button" @click="editorOpen = !editorOpen">
        {{ editorOpen ? '收起创建表单' : '新建项目' }}
      </button>
    </header>

    <section v-if="editorOpen" class="editor-panel" aria-labelledby="create-project-title">
      <div class="panel-title-row">
        <h2 id="create-project-title">创建项目</h2>
        <span>项目所有者将使用当前登录账号</span>
      </div>
      <div v-if="submitError" class="inline-alert is-error" role="alert">{{ submitError }}</div>
      <ProjectForm
        :submitting="projectStore.saving"
        submit-label="创建项目"
        @submit="createProject"
        @cancel="editorOpen = false"
      />
    </section>

    <div v-if="searchQuery" class="search-result-bar">
      <span>“{{ route.query.q }}”的当前页搜索结果：{{ visibleProjects.length }} 个</span>
      <RouterLink to="/projects">清除搜索</RouterLink>
    </div>

    <div v-if="projectStore.listError" class="inline-alert is-error" role="alert">
      <span>{{ projectStore.listError }}</span>
      <button type="button" @click="loadProjects">重试</button>
    </div>

    <div v-if="projectStore.listLoading" class="project-list-skeleton" aria-label="项目加载中">
      <span v-for="index in 6" :key="index" />
    </div>

    <section v-else-if="visibleProjects.length > 0" class="project-list-grid" aria-label="项目列表">
      <ProjectFlipCard
        v-for="(project, index) in visibleProjects"
        :key="project.id"
        :project="project"
        :image-url="getProjectCover(project.id, index)"
        @edit="editProject"
        @delete="removeProject"
      />
    </section>

    <section v-else class="empty-state wide-empty-state">
      <h2>{{ searchQuery ? '没有找到匹配项目' : '还没有项目' }}</h2>
      <p>{{ searchQuery ? '调整搜索词，或返回查看当前页全部项目。' : '创建第一个项目，开始记录代码实践。' }}</p>
      <button v-if="!searchQuery" class="primary-command" type="button" @click="editorOpen = true">
        创建项目
      </button>
    </section>

    <nav v-if="projectStore.page.total_pages > 1" class="pagination" aria-label="项目分页">
      <button
        type="button"
        :disabled="projectStore.page.page <= 1 || projectStore.listLoading"
        @click="changePage(projectStore.page.page - 1)"
      >
        上一页
      </button>
      <span>第 {{ projectStore.page.page }} / {{ projectStore.page.total_pages }} 页</span>
      <button
        type="button"
        :disabled="projectStore.page.page >= projectStore.page.total_pages || projectStore.listLoading"
        @click="changePage(projectStore.page.page + 1)"
      >
        下一页
      </button>
    </nav>
  </div>
</template>
