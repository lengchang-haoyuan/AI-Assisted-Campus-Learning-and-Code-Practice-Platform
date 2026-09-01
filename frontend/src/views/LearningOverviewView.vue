<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getApiErrorMessage } from '@/api/errors'
import CourseEditor from '@/components/CourseEditor.vue'
import LearningNav from '@/components/LearningNav.vue'
import LearningPlanEditor from '@/components/LearningPlanEditor.vue'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import { courseStatusLabels, planStatusLabels } from '@/domain/learning'
import { useLearningStore } from '@/stores/learning'
import { useProjectStore } from '@/stores/projects'
import type {
  CourseCreateInput,
  CourseResponse,
  LearningPlanCreateInput,
  LearningPlanResponse,
} from '@/types/learning'

const learningStore = useLearningStore()
const projectStore = useProjectStore()
const viewMode = ref('plans')
const editorType = ref<'course' | 'plan' | null>(null)
const editingCourse = ref<CourseResponse | null>(null)
const editingPlan = ref<LearningPlanResponse | null>(null)
const modeOptions: LiquidTabOption[] = [
  { value: 'plans', label: '学习计划' },
  { value: 'courses', label: '课程档案' },
]
const activePlanCount = computed(
  () => learningStore.planPage.items.filter((plan) => plan.status === 'active').length,
)

async function loadOverview(): Promise<void> {
  await Promise.all([
    learningStore.fetchCourses({ page: 1, pageSize: 100 }),
    learningStore.fetchPlans({ page: 1, pageSize: 100 }),
    projectStore.fetchProjects({ page: 1, pageSize: 100 }),
  ])
}

function openCourseEditor(course: CourseResponse | null = null): void {
  editingCourse.value = course
  editorType.value = 'course'
}

function openPlanEditor(plan: LearningPlanResponse | null = null): void {
  editingPlan.value = plan
  editorType.value = 'plan'
}

function closeEditor(): void {
  editorType.value = null
  editingCourse.value = null
  editingPlan.value = null
}

async function saveCourse(input: CourseCreateInput): Promise<void> {
  const wasEditing = editingCourse.value !== null
  try {
    await learningStore.saveCourse(input, editingCourse.value?.id)
    closeEditor()
    await learningStore.fetchCourses({ page: 1, pageSize: 100 })
    ElMessage.success(wasEditing ? '课程已更新' : '课程已创建')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '课程保存失败，请重试'))
  }
}

async function savePlan(input: LearningPlanCreateInput): Promise<void> {
  const wasEditing = editingPlan.value !== null
  try {
    await learningStore.savePlan(input, editingPlan.value?.id)
    closeEditor()
    await learningStore.fetchPlans({ page: 1, pageSize: 100 })
    ElMessage.success(wasEditing ? '学习计划已更新' : '学习计划已创建')
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '学习计划保存失败，请重试'))
  }
}

async function removeCourse(course: CourseResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除课程“${course.name}”吗？已有计划和记录会保留，但不再关联此课程。`,
      '删除课程',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
    await learningStore.removeCourse(course.id)
    await learningStore.fetchCourses({ page: 1, pageSize: 100 })
    ElMessage.success('课程已删除')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '课程删除失败，请重试'))
    }
  }
}

async function removePlan(plan: LearningPlanResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除计划“${plan.title}”吗？计划内任务会保留为独立任务。`,
      '删除学习计划',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
    await learningStore.removePlan(plan.id)
    await learningStore.fetchPlans({ page: 1, pageSize: 100 })
    ElMessage.success('学习计划已删除')
  } catch (error: unknown) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '学习计划删除失败，请重试'))
    }
  }
}

onMounted(() => {
  void loadOverview().catch(() => undefined)
})
</script>

<template>
  <div class="page-shell workspace-page learning-page">
    <LearningNav />
    <header class="learning-hero">
      <div>
        <p class="page-kicker">Learning Studio</p>
        <h1>课程与学习计划</h1>
        <p>把课程目标、项目实践和每天的行动放进同一条学习路径。</p>
      </div>
      <div class="learning-hero__stats" aria-label="学习概览">
        <div><NumberRoller :value="learningStore.coursePage.total" /><span>门课程</span></div>
        <div><NumberRoller :value="activePlanCount" /><span>个进行中计划</span></div>
      </div>
    </header>

    <section v-if="editorType" class="workspace-panel workspace-editor learning-editor" :aria-label="editorType === 'course' ? '课程编辑器' : '计划编辑器'">
      <div class="panel-title-row">
        <h2>{{ editorType === 'course' ? (editingCourse ? '编辑课程' : '创建课程') : (editingPlan ? '编辑计划' : '创建计划') }}</h2>
        <button class="text-command" type="button" @click="closeEditor">关闭</button>
      </div>
      <CourseEditor
        v-if="editorType === 'course'"
        :key="editingCourse?.id ?? 'new-course'"
        :initial-value="editingCourse"
        :submitting="learningStore.saving"
        @submit="saveCourse"
        @cancel="closeEditor"
      />
      <LearningPlanEditor
        v-else
        :key="editingPlan?.id ?? 'new-plan'"
        :initial-value="editingPlan"
        :courses="learningStore.coursePage.items"
        :projects="projectStore.projects"
        :submitting="learningStore.saving"
        @submit="savePlan"
        @cancel="closeEditor"
      />
    </section>

    <div class="learning-toolbar">
      <LiquidTabs v-model="viewMode" :options="modeOptions" ariaLabel="课程与计划视图" />
      <div>
        <button class="secondary-command" type="button" @click="openCourseEditor()">新建课程</button>
        <button class="primary-command" type="button" @click="openPlanEditor()">新建计划</button>
      </div>
    </div>

    <template v-if="viewMode === 'plans'">
      <div v-if="learningStore.planError" class="inline-alert is-error" role="alert"><span>{{ learningStore.planError }}</span><button type="button" @click="learningStore.fetchPlans({ page: 1, pageSize: 100 })">重试</button></div>
      <div v-if="learningStore.loadingPlans" class="learning-grid learning-grid--loading"><span v-for="index in 4" :key="index" /></div>
      <section v-else-if="learningStore.planPage.items.length" class="learning-grid" aria-label="学习计划列表">
        <article v-for="plan in learningStore.planPage.items" :key="plan.id" class="learning-plan-card">
          <div class="panel-title-row"><span class="status-chip">{{ planStatusLabels[plan.status] }}</span><strong>{{ plan.progress }}%</strong></div>
          <h2>{{ plan.title }}</h2>
          <p>{{ plan.description || '暂未填写计划说明。' }}</p>
          <div class="learning-plan-card__refs"><span>{{ plan.course?.name || '未关联课程' }}</span><span>{{ plan.project?.name || '未关联项目' }}</span></div>
          <div class="learning-progress" :aria-label="`计划进度 ${plan.progress}%`"><span :style="{ transform: `scaleX(${plan.progress / 100})` }" /></div>
          <footer>
            <small>{{ plan.start_date || '未设开始' }} 至 {{ plan.end_date || '未设结束' }}</small>
            <div><button class="text-command" type="button" @click="openPlanEditor(plan)">编辑</button><button class="text-command danger-text-command" type="button" :disabled="learningStore.actionKey === `plan:${plan.id}`" @click="removePlan(plan)">删除</button></div>
          </footer>
        </article>
      </section>
      <section v-else class="empty-state"><h2>还没有学习计划</h2><p>先选择一门课程或一个项目，再建立可以执行的日期范围。</p><button class="primary-command" type="button" @click="openPlanEditor()">创建第一个计划</button></section>
    </template>

    <template v-else>
      <div v-if="learningStore.courseError" class="inline-alert is-error" role="alert"><span>{{ learningStore.courseError }}</span><button type="button" @click="learningStore.fetchCourses({ page: 1, pageSize: 100 })">重试</button></div>
      <div v-if="learningStore.loadingCourses" class="learning-course-list learning-grid--loading"><span v-for="index in 4" :key="index" /></div>
      <section v-else-if="learningStore.coursePage.items.length" class="learning-course-list" aria-label="课程列表">
        <article v-for="course in learningStore.coursePage.items" :key="course.id">
          <div class="learning-course-list__code">{{ course.code || 'COURSE' }}</div>
          <div><span class="status-chip">{{ courseStatusLabels[course.status] }}</span><h2>{{ course.name }}</h2><p>{{ course.description || course.instructor || '暂未填写课程说明。' }}</p></div>
          <div class="learning-row-actions"><button class="text-command" type="button" @click="openCourseEditor(course)">编辑</button><button class="text-command danger-text-command" type="button" :disabled="learningStore.actionKey === `course:${course.id}`" @click="removeCourse(course)">删除</button></div>
        </article>
      </section>
      <section v-else class="empty-state"><h2>还没有课程档案</h2><p>创建课程后，就可以在学习计划和记录中引用它。</p><button class="primary-command" type="button" @click="openCourseEditor()">创建第一门课程</button></section>
    </template>
  </div>
</template>
