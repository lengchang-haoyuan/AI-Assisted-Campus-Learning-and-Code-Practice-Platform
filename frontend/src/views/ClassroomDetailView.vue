<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { listProjects } from '@/api/projects'
import {
  addClassMember,
  createTeachingAssignment,
  getTeachingClass,
  listClassMembers,
  listTeachingAssignments,
  updateClassMember,
  updateTeachingClass,
} from '@/api/teaching'
import type { ProjectResponse } from '@/types/project'
import type { ClassMemberResponse, ClassMemberRole, TeachingAssignmentResponse, TeachingClassResponse } from '@/types/teaching'

const route = useRoute()
const router = useRouter()
const classId = Number(route.params.classId)
const teachingClass = ref<TeachingClassResponse | null>(null)
const members = ref<ClassMemberResponse[]>([])
const assignments = ref<TeachingAssignmentResponse[]>([])
const projects = ref<ProjectResponse[]>([])
const loading = ref(true)
const errorMessage = ref<string | null>(null)
const actionKey = ref<string | null>(null)
const showClassEditor = ref(false)
const showAssignmentEditor = ref(false)

const classForm = reactive({ name: '', course_title: '', term_label: '' })
const memberForm = reactive<{ campus_membership_id: number | null; member_role: ClassMemberRole }>({ campus_membership_id: null, member_role: 'student' })
const assignmentForm = reactive({
  title: '',
  instructions: '',
  learning_objectives: '',
  acceptance_criteria: '',
  due_at: '',
  source_project_id: null as number | null,
})

const canLeave = computed(() => teachingClass.value?.viewer_role === 'student' && teachingClass.value.status === 'active')

function formatDate(value: string | null): string {
  if (!value) return '未设置'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function resetClassForm(value: TeachingClassResponse): void {
  classForm.name = value.name
  classForm.course_title = value.course_title
  classForm.term_label = value.term_label
}

async function loadPage(): Promise<void> {
  if (!Number.isInteger(classId) || classId < 1) {
    errorMessage.value = '教学班地址无效'
    loading.value = false
    return
  }
  loading.value = true
  errorMessage.value = null
  try {
    const value = await getTeachingClass(classId)
    teachingClass.value = value
    resetClassForm(value)
    const requests: Promise<unknown>[] = []
    if (value.viewer_role !== 'administrator') {
      requests.push(listTeachingAssignments(classId).then((page) => { assignments.value = page.items }))
    }
    if (value.can_view_members) {
      requests.push(listClassMembers(classId).then((page) => { members.value = page.items }))
    }
    if (value.can_create_assignments) {
      requests.push(listProjects({ page: 1, pageSize: 100 }).then((page) => { projects.value = page.items }))
    }
    await Promise.all(requests)
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '教学班详情加载失败')
  } finally {
    loading.value = false
  }
}

async function saveClass(): Promise<void> {
  if (!teachingClass.value || actionKey.value) return
  actionKey.value = 'class'
  try {
    teachingClass.value = await updateTeachingClass(classId, {
      expected_revision: teachingClass.value.revision,
      ...classForm,
    })
    showClassEditor.value = false
    ElMessage.success('班级资料已更新')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '班级资料保存失败'))
  } finally { actionKey.value = null }
}

async function archiveClass(): Promise<void> {
  if (!teachingClass.value || actionKey.value) return
  try {
    await ElMessageBox.confirm('归档后班级和任务仅保留只读访问，确定继续吗？', '归档教学班', { type: 'warning' })
    actionKey.value = 'archive-class'
    teachingClass.value = await updateTeachingClass(classId, { expected_revision: teachingClass.value.revision, status: 'archived' })
    ElMessage.success('教学班已归档')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '班级归档失败'))
  } finally { actionKey.value = null }
}

async function addMember(): Promise<void> {
  if (!memberForm.campus_membership_id || actionKey.value) return
  actionKey.value = 'add-member'
  try {
    await addClassMember(classId, memberForm.campus_membership_id, memberForm.member_role)
    members.value = (await listClassMembers(classId)).items
    memberForm.campus_membership_id = null
    ElMessage.success('班级成员已加入')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '成员加入失败'))
  } finally { actionKey.value = null }
}

async function removeMember(member: ClassMemberResponse): Promise<void> {
  if (actionKey.value) return
  try {
    await ElMessageBox.confirm(`确定将“${member.username}”移出班级吗？`, '移除成员', { type: 'warning' })
    actionKey.value = `member:${member.id}`
    await updateClassMember(classId, member.id, member.revision, 'removed')
    members.value = (await listClassMembers(classId)).items
    ElMessage.success('成员已移除')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '成员移除失败'))
  } finally { actionKey.value = null }
}

async function leaveClass(): Promise<void> {
  const value = teachingClass.value
  if (!value?.viewer_member_id || !value.viewer_member_revision || actionKey.value) return
  try {
    await ElMessageBox.confirm('退出后将立即失去班级和任务访问，确定继续吗？', '退出教学班', { type: 'warning' })
    actionKey.value = 'leave'
    await updateClassMember(classId, value.viewer_member_id, value.viewer_member_revision, 'left')
    ElMessage.success('已退出教学班')
    await router.replace({ name: 'campus-classes' })
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(getApiErrorMessage(error, '退出班级失败'))
  } finally { actionKey.value = null }
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

async function createAssignment(): Promise<void> {
  if (actionKey.value || !assignmentForm.due_at) return
  actionKey.value = 'assignment'
  try {
    await createTeachingAssignment(classId, {
      title: assignmentForm.title.trim(),
      instructions: assignmentForm.instructions.trim(),
      learning_objectives: lines(assignmentForm.learning_objectives),
      acceptance_criteria: lines(assignmentForm.acceptance_criteria),
      due_at: new Date(assignmentForm.due_at).toISOString(),
      source_project_id: assignmentForm.source_project_id,
    })
    Object.assign(assignmentForm, { title: '', instructions: '', learning_objectives: '', acceptance_criteria: '', due_at: '', source_project_id: null })
    assignments.value = (await listTeachingAssignments(classId)).items
    showAssignmentEditor.value = false
    ElMessage.success('任务草稿已保存')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '任务草稿保存失败'))
  } finally { actionKey.value = null }
}

onMounted(() => void loadPage())
</script>

<template>
  <div class="page-shell teaching-page">
    <RouterLink class="back-link" to="/campus/classes">← 返回教学班</RouterLink>
    <div v-if="errorMessage" class="inline-alert is-error" role="alert"><span>{{ errorMessage }}</span><button type="button" @click="loadPage">重试</button></div>
    <div v-if="loading" class="teaching-detail-loading"><span v-for="index in 4" :key="index" /></div>
    <template v-else-if="teachingClass">
      <header class="teaching-detail-hero">
        <div><p class="page-kicker">{{ teachingClass.term_label }}</p><h1>{{ teachingClass.name }}</h1><p>{{ teachingClass.course_title }}</p></div>
        <div class="form-actions">
          <button v-if="teachingClass.can_edit" class="secondary-command" type="button" @click="showClassEditor = !showClassEditor">编辑资料</button>
          <button v-if="teachingClass.can_manage_members" class="danger-command" type="button" :disabled="!!actionKey || teachingClass.status === 'archived'" @click="archiveClass">归档班级</button>
          <button v-if="canLeave" class="danger-command" type="button" :disabled="!!actionKey" @click="leaveClass">退出班级</button>
        </div>
      </header>

      <section v-if="showClassEditor" class="teaching-panel">
        <form class="form-grid" @submit.prevent="saveClass">
          <label class="field"><span>班级名称</span><input v-model.trim="classForm.name" required minlength="2" maxlength="120" /></label>
          <label class="field"><span>课程名称</span><input v-model.trim="classForm.course_title" required minlength="2" maxlength="120" /></label>
          <label class="field"><span>学期</span><input v-model.trim="classForm.term_label" required minlength="2" maxlength="60" /></label>
          <div class="form-actions teaching-form-action"><button class="primary-command" type="submit" :disabled="!!actionKey">保存资料</button></div>
        </form>
      </section>

      <section v-if="teachingClass.can_view_members" class="teaching-panel">
        <div class="teaching-panel__heading"><div><span>成员管理</span><h2>班级成员</h2></div><p>使用成员本人校园身份编号加入，角色必须与核验身份一致。</p></div>
        <form v-if="teachingClass.status === 'active'" class="teaching-member-form" @submit.prevent="addMember">
          <label class="field"><span>校园身份编号</span><input v-model.number="memberForm.campus_membership_id" type="number" min="1" required /></label>
          <label class="field"><span>班级角色</span><select v-model="memberForm.member_role"><option value="student">学生</option><option v-if="teachingClass.viewer_role === 'administrator'" value="teacher">教师</option></select></label>
          <button class="primary-command" type="submit" :disabled="!!actionKey">加入班级</button>
        </form>
        <div class="teaching-member-list">
          <article v-for="member in members" :key="member.id">
            <div><strong>{{ member.username }}</strong><small>校园身份 #{{ member.campus_membership_id }} · {{ member.member_role === 'teacher' ? '教师' : '学生' }}</small></div>
            <span class="status-chip">{{ member.status === 'active' ? '有效' : member.status === 'left' ? '已退出' : '已移除' }}</span>
            <button v-if="teachingClass.can_manage_members && member.status === 'active' && (member.member_role === 'student' || teachingClass.viewer_role === 'administrator')" class="text-command danger-text-command" type="button" :disabled="!!actionKey" @click="removeMember(member)">移除</button>
          </article>
        </div>
      </section>

      <section class="teaching-panel">
        <div class="teaching-panel__heading">
          <div><span>教学任务</span><h2>{{ teachingClass.viewer_role === 'student' ? '已发布任务' : '任务列表' }}</h2></div>
          <button v-if="teachingClass.can_create_assignments" class="primary-command" type="button" @click="showAssignmentEditor = !showAssignmentEditor">{{ showAssignmentEditor ? '收起表单' : '新建任务' }}</button>
        </div>
        <form v-if="showAssignmentEditor" class="form-grid teaching-assignment-form" @submit.prevent="createAssignment">
          <label class="field field-span-2"><span>任务标题</span><input v-model.trim="assignmentForm.title" required minlength="2" maxlength="160" /></label>
          <label class="field field-span-2"><span>任务说明</span><textarea v-model.trim="assignmentForm.instructions" required minlength="10" maxlength="20000" /></label>
          <label class="field"><span>学习目标（每行一项）</span><textarea v-model="assignmentForm.learning_objectives" required /></label>
          <label class="field"><span>交付要求（每行一项）</span><textarea v-model="assignmentForm.acceptance_criteria" required /></label>
          <label class="field"><span>截止时间（本地时区）</span><input v-model="assignmentForm.due_at" type="datetime-local" required /></label>
          <label class="field"><span>项目模板（可选快照）</span><select v-model="assignmentForm.source_project_id"><option :value="null">不引用项目</option><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label>
          <div class="form-actions field-span-2"><button class="primary-command" type="submit" :disabled="!!actionKey">{{ actionKey === 'assignment' ? '正在保存' : '保存草稿' }}</button></div>
        </form>
        <div v-if="teachingClass.viewer_role === 'administrator'" class="teaching-note">管理员可以管理班级与成员，但不读取教学任务正文。</div>
        <div v-else-if="assignments.length" class="teaching-assignment-list">
          <RouterLink v-for="assignment in assignments" :key="assignment.id" :to="`/campus/assignments/${assignment.id}`">
            <div><span class="status-chip">{{ { draft: '草稿', published: '已发布', closed: '已关闭', archived: '已归档' }[assignment.status] }}</span><h3>{{ assignment.title }}</h3><p>截止：{{ formatDate(assignment.due_at) }}</p></div><strong>v{{ assignment.revision }} →</strong>
          </RouterLink>
        </div>
        <div v-else class="teaching-note">{{ teachingClass.viewer_role === 'student' ? '教师还没有发布任务。' : '还没有教学任务。' }}</div>
      </section>
    </template>
  </div>
</template>
