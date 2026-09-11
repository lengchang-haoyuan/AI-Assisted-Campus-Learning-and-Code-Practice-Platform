<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { isAxiosError } from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { getProjectPublication, requestProjectPublication, withdrawPublication } from '@/api/community'
import { getProjectCover } from '@/assets/projectCovers'
import ProjectForm from '@/components/ProjectForm.vue'
import { difficultyLabels, formatProjectTime, formatRequirement, getProjectStack, statusLabels } from '@/domain/projects'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/projects'
import type { PublicationKind, PublicationResponse } from '@/types/community'
import type { CampusRole } from '@/types/campus'
import type { ProjectCreateInput } from '@/types/project'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const projectStore = useProjectStore()
const editMode = ref(route.query.edit === '1')
const submitError = ref<string | null>(null)
const publicationOpen = ref(false)
const publicationLoading = ref(false)
const publicationSaving = ref(false)
const publicationError = ref<string | null>(null)
const publication = ref<PublicationResponse | null>(null)
const campusRole = ref<CampusRole | null>(null)
const publicationTags = ref('')
const publicationKind = ref<PublicationKind>('work')
const attribution = ref('')
const sourceLicense = ref('原创作品；如引用第三方内容，请在项目说明中列明来源与许可。')
const aiStatement = ref('未使用 AI 辅助；如有使用，将如实说明用途和人工核验范围。')
const humanReview = ref('')
const requestKey = ref('')

const publicationStatusLabels: Record<PublicationResponse['status'], string> = {
  legacy_review_required: '历史作品待补审', pending_review: '等待审核', approved: '审核通过',
  returned: '已退回', withdrawn: '已撤回', taken_down: '已下架',
}
const projectId = computed(() => {
  const value = Number(route.params.id)
  return Number.isInteger(value) && value > 0 ? value : null
})
const project = computed(() => projectStore.currentProject)
const stack = computed(() => (project.value ? getProjectStack(project.value) : []))
const canSubmitPublication = computed(() => publication.value?.pending_version_number == null)
const canWithdrawPublication = computed(() => Boolean(publication.value?.pending_version_number || publication.value?.public_version_number))

function newRequestKey(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().replaceAll('-', '')
    : `publish_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

function fillPublicationForm(): void {
  const version = publication.value?.pending_version ?? publication.value?.public_version
  if (version) {
    publicationTags.value = version.tags.join('，')
    publicationKind.value = version.kind
    attribution.value = version.attribution ?? authStore.currentUser?.username ?? ''
    sourceLicense.value = version.source_license_statement ?? sourceLicense.value
    aiStatement.value = version.ai_assistance_statement ?? aiStatement.value
    humanReview.value = version.human_review_statement ?? ''
    return
  }
  publicationTags.value = project.value?.tags.map((tag) => tag.name).join('，') ?? ''
  attribution.value = authStore.currentUser?.username ?? ''
}

async function loadPublication(): Promise<void> {
  if (projectId.value === null) return
  publicationLoading.value = true
  publicationError.value = null
  try {
    publication.value = await getProjectPublication(projectId.value)
  } catch (error: unknown) {
    if (isAxiosError(error) && error.response?.status === 404) publication.value = null
    else publicationError.value = getApiErrorMessage(error, '发布进度加载失败')
  } finally {
    publicationLoading.value = false
    fillPublicationForm()
  }
}

async function loadProject(): Promise<void> {
  if (projectId.value === null) return
  try {
    await projectStore.fetchProject(projectId.value)
    await loadPublication()
  } catch {
    // Store 已保存可重试提示。
  }
}

function parsePublicationTags(): string[] | null {
  const tags = publicationTags.value.split(/[,，\n]/).map((tag) => tag.trim())
    .filter((tag, index, values) => tag && values.findIndex((value) => value.toLowerCase() === tag.toLowerCase()) === index)
  if (tags.length > 5 || tags.some((tag) => tag.length > 50)) {
    publicationError.value = '标签最多 5 个，每个不能超过 50 个字符'
    return null
  }
  return tags
}

async function submitPublication(): Promise<void> {
  if (!project.value || projectId.value === null) return
  publicationError.value = null
  const tags = parsePublicationTags()
  if (!tags) return
  if (!attribution.value.trim() || !sourceLicense.value.trim() || !aiStatement.value.trim()) {
    publicationError.value = '请完整填写署名、来源或许可说明、AI 辅助使用声明'
    return
  }
  if (publicationKind.value === 'practice_template' && !humanReview.value.trim()) {
    publicationError.value = '实践项目模板必须填写人工审阅说明'
    return
  }
  publicationSaving.value = true
  requestKey.value ||= newRequestKey()
  try {
    publication.value = await requestProjectPublication(projectId.value, {
      request_key: requestKey.value,
      expected_project_updated_at: project.value.updated_at,
      kind: publicationKind.value,
      tags,
      attribution: attribution.value.trim(),
      source_license_statement: sourceLicense.value.trim(),
      ai_assistance_statement: aiStatement.value.trim(),
      ...(humanReview.value.trim() ? { human_review_statement: humanReview.value.trim() } : {}),
    })
    requestKey.value = ''
    publicationOpen.value = false
    ElMessage.success('发布申请已提交，审核通过前不会公开新内容')
  } catch (error: unknown) {
    publicationError.value = getApiErrorMessage(error, '发布申请失败；刷新前再次提交会沿用同一请求，避免重复版本')
  } finally { publicationSaving.value = false }
}

async function withdrawCurrentPublication(): Promise<void> {
  if (!publication.value) return
  try {
    const { value } = await ElMessageBox.prompt('请说明撤回原因（至少 3 个字符）。公开版本撤回后将无法继续浏览。', '撤回发布', {
      confirmButtonText: '确认撤回', cancelButtonText: '取消', inputValidator: (text) => text.trim().length >= 3 || '请填写至少 3 个字符',
    })
    publication.value = await withdrawPublication(publication.value.id, publication.value.revision, value.trim())
    publicationOpen.value = false
    ElMessage.success('发布已撤回')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '撤回失败，请刷新后重试'))
  }
}

async function updateProject(input: ProjectCreateInput): Promise<void> {
  if (projectId.value === null) return
  submitError.value = null
  try {
    await projectStore.updateProject(projectId.value, input)
    editMode.value = false
    await loadPublication()
    ElMessage.success('项目已更新；已公开内容仍使用审核通过的快照')
  } catch (error: unknown) { submitError.value = getApiErrorMessage(error, '项目更新失败，请检查输入后重试') }
}

async function removeProject(): Promise<void> {
  if (!project.value) return
  try {
    await ElMessageBox.confirm(`删除“${project.value.name}”后无法恢复。`, '确认删除项目', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'el-button--danger' })
    await projectStore.deleteProject(project.value.id)
    ElMessage.success('项目已删除')
    await router.replace({ name: 'projects' })
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除失败；有公开或待审版本时需先撤回'))
  }
}

onMounted(async () => {
  try { campusRole.value = (await getCampusMe()).membership?.role ?? null } catch { campusRole.value = null }
  await loadProject()
})
onBeforeUnmount(() => projectStore.clearCurrentProject())
</script>

<template>
  <div class="page-shell project-detail-page">
    <RouterLink class="back-link" to="/projects">返回项目库</RouterLink>
    <div v-if="projectId === null" class="inline-alert is-error" role="alert">项目地址无效。</div>
    <div v-else-if="projectStore.detailLoading" class="detail-skeleton" aria-label="项目加载中"><span /><span /><span /></div>
    <div v-else-if="projectStore.detailError" class="inline-alert is-error" role="alert"><span>{{ projectStore.detailError }}</span><button type="button" @click="loadProject">重试</button></div>

    <template v-else-if="project">
      <header class="project-detail-header">
        <div><div class="tag-row"><span class="status-chip" :data-status="project.status">{{ statusLabels[project.status] }}</span><span class="tech-tag">{{ difficultyLabels[project.difficulty] }}</span></div><h1>{{ project.name }}</h1><p>{{ project.description || '这个项目还没有补充说明。' }}</p></div>
        <div class="detail-actions">
          <RouterLink class="secondary-command" :to="`/projects/${project.id}/ai`">AI 工作台</RouterLink>
          <RouterLink v-if="publication?.public_version_number" class="primary-command" :to="`/community/projects/${project.id}`">查看社区快照</RouterLink>
          <button class="primary-command" type="button" :disabled="publicationLoading" @click="publicationOpen = !publicationOpen">{{ publicationOpen ? '收起申请表' : publication ? '管理发布' : '申请发布' }}</button>
          <button class="secondary-command" type="button" @click="editMode = !editMode">{{ editMode ? '退出编辑' : '编辑项目' }}</button>
          <button class="danger-command" type="button" :disabled="projectStore.saving" @click="removeProject">删除项目</button>
        </div>
      </header>

      <section v-if="publication || publicationError" class="publication-status-card" aria-live="polite">
        <div v-if="publication"><strong>{{ publicationStatusLabels[publication.status] }}</strong><span>发布版本 {{ publication.public_version_number ?? '—' }} · 待审版本 {{ publication.pending_version_number ?? '—' }}</span></div>
        <p v-if="publication?.public_version_number">对私人项目的后续修改不会直接替换社区内容；需再次提交并审核。</p>
        <div v-if="publicationError" class="inline-alert is-error" role="alert">{{ publicationError }}</div>
      </section>

      <section v-if="publicationOpen" class="publication-panel" aria-labelledby="publication-title">
        <div class="panel-title-row"><h2 id="publication-title">校园社区发布申请</h2><span>审核通过后公开固定快照</span></div>
        <div v-if="!canSubmitPublication" class="inline-alert">已有版本等待审核，暂不能重复提交。</div>
        <div class="publication-form-grid">
          <label class="field"><span>内容类型</span><select v-model="publicationKind" :disabled="!canSubmitPublication"><option value="work">校园作品</option><option v-if="campusRole === 'teacher'" value="practice_template">实践项目模板</option></select></label>
          <label class="field"><span>署名</span><input v-model="attribution" maxlength="160" :disabled="!canSubmitPublication" /></label>
          <label class="field is-wide"><span>项目标签</span><input v-model="publicationTags" maxlength="254" :disabled="!canSubmitPublication" placeholder="例如：Vue，校园服务" /><small>逗号分隔，最多 5 个</small></label>
          <label class="field is-wide"><span>来源或许可说明</span><textarea v-model="sourceLicense" rows="3" maxlength="500" :disabled="!canSubmitPublication" /></label>
          <label class="field is-wide"><span>AI 辅助使用声明</span><textarea v-model="aiStatement" rows="3" maxlength="1000" :disabled="!canSubmitPublication" /></label>
          <label v-if="publicationKind === 'practice_template'" class="field is-wide"><span>人工审阅说明</span><textarea v-model="humanReview" rows="3" maxlength="1000" :disabled="!canSubmitPublication" placeholder="说明审阅人、审阅范围和依据" /></label>
        </div>
        <div v-if="publicationError" class="inline-alert is-error" role="alert">{{ publicationError }}</div>
        <div class="form-actions">
          <button v-if="canWithdrawPublication" class="danger-command" type="button" :disabled="publicationSaving" @click="withdrawCurrentPublication">撤回发布</button>
          <RouterLink class="secondary-command" to="/community/governance">查看治理进度</RouterLink>
          <button class="primary-command" type="button" :disabled="publicationSaving || !canSubmitPublication" @click="submitPublication">{{ publicationSaving ? '正在提交…' : publication?.public_version_number ? '提交更新审核' : '提交发布申请' }}</button>
        </div>
      </section>

      <section v-if="editMode" class="editor-panel" aria-labelledby="edit-project-title"><h2 id="edit-project-title">编辑项目信息</h2><div v-if="submitError" class="inline-alert is-error" role="alert">{{ submitError }}</div><ProjectForm :initial-value="project" :submitting="projectStore.saving" submit-label="保存修改" @submit="updateProject" @cancel="editMode = false" /></section>
      <div v-else class="project-detail-grid">
        <section class="project-overview"><img :src="getProjectCover(project.id)" :alt="`${project.name} 项目封面`" /><div class="code-preview" aria-label="项目配置摘要"><span>project = {</span><span>&nbsp;&nbsp;name: "{{ project.name }}",</span><span>&nbsp;&nbsp;status: "{{ project.status }}",</span><span>&nbsp;&nbsp;owner: "{{ project.owner.username }}"</span><span>}</span></div></section>
        <section class="detail-section"><h2>技术栈</h2><div class="tag-row"><span v-for="technology in stack" :key="technology" class="tech-tag">{{ technology }}</span><span v-if="stack.length === 0" class="tech-tag is-muted">暂未设置</span></div><dl class="detail-facts"><div><dt>主要语言</dt><dd>{{ project.language || '未设置' }}</dd></div><div><dt>核心框架</dt><dd>{{ project.framework || '未设置' }}</dd></div><div><dt>创建时间</dt><dd>{{ formatProjectTime(project.created_at) }}</dd></div><div><dt>更新时间</dt><dd>{{ formatProjectTime(project.updated_at) }}</dd></div></dl></section>
        <section class="detail-section"><h2>项目需求</h2><ul v-if="project.requirements?.length" class="requirement-list"><li v-for="(requirement, index) in project.requirements" :key="index">{{ formatRequirement(requirement) }}</li></ul><p v-else class="muted-copy">暂未填写项目需求。</p></section>
        <section class="detail-section"><h2>交付要求</h2><p class="long-copy">{{ project.output_requirement || '暂未填写交付要求。' }}</p></section>
      </div>
    </template>
  </div>
</template>
