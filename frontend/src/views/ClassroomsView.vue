<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getCampusMe } from '@/api/campus'
import { getApiErrorMessage } from '@/api/errors'
import { createTeachingClass, listTeachingClasses } from '@/api/teaching'
import type { CampusRole } from '@/types/campus'
import type { TeachingClassResponse } from '@/types/teaching'

const classes = ref<TeachingClassResponse[]>([])
const campusRole = ref<CampusRole | null>(null)
const loading = ref(true)
const submitting = ref(false)
const errorMessage = ref<string | null>(null)
const page = ref(1)
const totalPages = ref(0)
const classForm = reactive({ name: '', course_title: '', term_label: '' })

const roleLabels: Record<string, string> = {
  administrator: '管理员视图',
  teacher: '教师视图',
  student: '学生视图',
}

async function loadClasses(targetPage = page.value): Promise<void> {
  loading.value = true
  errorMessage.value = null
  try {
    const membership = (await getCampusMe()).membership
    campusRole.value = membership?.status === 'active' ? membership.role : null
    if (!campusRole.value) {
      classes.value = []
      totalPages.value = 0
      return
    }
    const result = await listTeachingClasses(targetPage)
    classes.value = result.items
    page.value = result.page
    totalPages.value = result.total_pages
  } catch (error: unknown) {
    errorMessage.value = getApiErrorMessage(error, '教学班加载失败')
  } finally {
    loading.value = false
  }
}

async function createClass(): Promise<void> {
  if (submitting.value) return
  submitting.value = true
  try {
    const created = await createTeachingClass({ ...classForm })
    classForm.name = ''
    classForm.course_title = ''
    classForm.term_label = ''
    await loadClasses(1)
    ElMessage.success(`教学班“${created.name}”已创建`)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '教学班创建失败'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => void loadClasses())
</script>

<template>
  <div class="page-shell teaching-page">
    <header class="page-header teaching-header">
      <div>
        <p class="page-kicker">Campus Practice</p>
        <h1>教学班</h1>
        <p>教师布置班级任务，学生查看已发布内容；个人课程与个人任务保持独立。</p>
      </div>
      <span v-if="campusRole" class="teaching-role-chip">{{ roleLabels[campusRole] }}</span>
    </header>

    <div v-if="errorMessage" class="inline-alert is-error" role="alert">
      <span>{{ errorMessage }}</span><button type="button" @click="loadClasses()">重试</button>
    </div>

    <section v-if="campusRole === 'teacher'" class="teaching-panel teaching-create-panel" aria-labelledby="create-class-title">
      <div class="teaching-panel__heading">
        <div><span>教师操作</span><h2 id="create-class-title">创建教学班</h2></div>
        <p>创建后你会成为该班的首位教师。</p>
      </div>
      <form class="form-grid" @submit.prevent="createClass">
        <label class="field"><span>班级名称</span><input v-model.trim="classForm.name" required minlength="2" maxlength="120" placeholder="例如：软件工程 1 班" /></label>
        <label class="field"><span>课程名称</span><input v-model.trim="classForm.course_title" required minlength="2" maxlength="120" placeholder="例如：项目实践" /></label>
        <label class="field"><span>学期</span><input v-model.trim="classForm.term_label" required minlength="2" maxlength="60" placeholder="例如：2026 秋季" /></label>
        <div class="form-actions teaching-form-action"><button class="primary-command" type="submit" :disabled="submitting">{{ submitting ? '正在创建' : '创建教学班' }}</button></div>
      </form>
    </section>

    <div v-if="loading" class="teaching-grid teaching-grid--loading" aria-label="正在加载教学班"><span v-for="index in 4" :key="index" /></div>
    <section v-else-if="!campusRole" class="empty-state">
      <h2>还没有有效校园身份</h2><p>先使用经过核验的校园邀请加入试点。</p><RouterLink class="primary-command" to="/campus/join">查看校园身份</RouterLink>
    </section>
    <section v-else-if="classes.length" class="teaching-grid" aria-label="教学班列表">
      <RouterLink v-for="item in classes" :key="item.id" class="teaching-class-card" :to="`/campus/classes/${item.id}`">
        <div class="teaching-card-topline"><span class="status-chip">{{ item.status === 'active' ? '进行中' : '已归档' }}</span><small>修订 v{{ item.revision }}</small></div>
        <h2>{{ item.name }}</h2>
        <p>{{ item.course_title }}</p>
        <footer><span>{{ item.term_label }}</span><strong>{{ roleLabels[item.viewer_role] }} →</strong></footer>
      </RouterLink>
    </section>
    <section v-else class="empty-state"><h2>暂无可访问的教学班</h2><p>{{ campusRole === 'teacher' ? '可以在上方创建第一个教学班。' : '加入班级后，已发布任务会出现在这里。' }}</p></section>

    <nav v-if="totalPages > 1" class="teaching-pagination" aria-label="教学班分页">
      <button class="secondary-command compact-command" type="button" :disabled="page <= 1 || loading" @click="loadClasses(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <button class="secondary-command compact-command" type="button" :disabled="page >= totalPages || loading" @click="loadClasses(page + 1)">下一页</button>
    </nav>
  </div>
</template>
