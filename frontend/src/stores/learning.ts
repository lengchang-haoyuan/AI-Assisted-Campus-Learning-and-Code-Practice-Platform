import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  completeLearningTask,
  createCourse,
  createLearningRecord,
  createLearningTask,
  createPlan,
  deleteCourse,
  deleteLearningRecord,
  deleteLearningTask,
  deletePlan,
  listCourses,
  listLearningRecords,
  listLearningTasks,
  listPlans,
  updateCourse,
  updateLearningRecord,
  updateLearningTask,
  updatePlan,
} from '@/api/learning'
import { getApiErrorMessage } from '@/api/errors'
import type {
  CourseCreateInput,
  CourseListResponse,
  CourseUpdateInput,
  LearningPageQuery,
  LearningPlanCreateInput,
  LearningPlanListResponse,
  LearningPlanUpdateInput,
  LearningRecordCreateInput,
  LearningRecordListResponse,
  LearningRecordUpdateInput,
  LearningTaskCreateInput,
  LearningTaskListResponse,
  LearningTaskUpdateInput,
} from '@/types/learning'

const EMPTY_COURSES: CourseListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}
const EMPTY_PLANS: LearningPlanListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}
const EMPTY_TASKS: LearningTaskListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}
const EMPTY_RECORDS: LearningRecordListResponse = {
  items: [], total: 0, page: 1, page_size: 20, total_pages: 0,
}

export const useLearningStore = defineStore('learning', () => {
  const coursePage = ref<CourseListResponse>({ ...EMPTY_COURSES })
  const planPage = ref<LearningPlanListResponse>({ ...EMPTY_PLANS })
  const taskPage = ref<LearningTaskListResponse>({ ...EMPTY_TASKS })
  const recordPage = ref<LearningRecordListResponse>({ ...EMPTY_RECORDS })
  const loadingCourses = ref(false)
  const loadingPlans = ref(false)
  const loadingTasks = ref(false)
  const loadingRecords = ref(false)
  const saving = ref(false)
  const actionKey = ref<string | null>(null)
  const courseError = ref<string | null>(null)
  const planError = ref<string | null>(null)
  const taskError = ref<string | null>(null)
  const recordError = ref<string | null>(null)

  async function fetchCourses(query: LearningPageQuery): Promise<void> {
    loadingCourses.value = true
    courseError.value = null
    try {
      coursePage.value = await listCourses(query)
    } catch (error: unknown) {
      courseError.value = getApiErrorMessage(error, '课程加载失败，请重试')
      throw error
    } finally {
      loadingCourses.value = false
    }
  }

  async function fetchPlans(query: LearningPageQuery): Promise<void> {
    loadingPlans.value = true
    planError.value = null
    try {
      planPage.value = await listPlans(query)
    } catch (error: unknown) {
      planError.value = getApiErrorMessage(error, '学习计划加载失败，请重试')
      throw error
    } finally {
      loadingPlans.value = false
    }
  }

  async function fetchTasks(
    query: LearningPageQuery,
    options: { scheduledDate?: string; planId?: number } = {},
  ): Promise<void> {
    loadingTasks.value = true
    taskError.value = null
    try {
      taskPage.value = await listLearningTasks(query, options)
    } catch (error: unknown) {
      taskError.value = getApiErrorMessage(error, '任务加载失败，请重试')
      throw error
    } finally {
      loadingTasks.value = false
    }
  }

  async function fetchRecords(query: LearningPageQuery): Promise<void> {
    loadingRecords.value = true
    recordError.value = null
    try {
      recordPage.value = await listLearningRecords(query)
    } catch (error: unknown) {
      recordError.value = getApiErrorMessage(error, '学习记录加载失败，请重试')
      throw error
    } finally {
      loadingRecords.value = false
    }
  }

  async function withSave(request: () => Promise<void>): Promise<void> {
    saving.value = true
    try {
      await request()
    } finally {
      saving.value = false
    }
  }

  async function saveCourse(
    input: CourseCreateInput | CourseUpdateInput,
    courseId?: number,
  ): Promise<void> {
    await withSave(async () => {
      if (courseId) await updateCourse(courseId, input)
      else await createCourse(input as CourseCreateInput)
    })
  }

  async function removeCourse(courseId: number): Promise<void> {
    actionKey.value = `course:${courseId}`
    try {
      await deleteCourse(courseId)
    } finally {
      actionKey.value = null
    }
  }

  async function savePlan(
    input: LearningPlanCreateInput | LearningPlanUpdateInput,
    planId?: number,
  ): Promise<void> {
    await withSave(async () => {
      if (planId) await updatePlan(planId, input)
      else await createPlan(input as LearningPlanCreateInput)
    })
  }

  async function removePlan(planId: number): Promise<void> {
    actionKey.value = `plan:${planId}`
    try {
      await deletePlan(planId)
    } finally {
      actionKey.value = null
    }
  }

  async function saveTask(
    input: LearningTaskCreateInput | LearningTaskUpdateInput,
    taskId?: number,
  ): Promise<void> {
    await withSave(async () => {
      if (taskId) await updateLearningTask(taskId, input)
      else await createLearningTask(input as LearningTaskCreateInput)
    })
  }

  async function completeTask(taskId: number): Promise<void> {
    actionKey.value = `task:${taskId}`
    try {
      const task = await completeLearningTask(taskId)
      taskPage.value = {
        ...taskPage.value,
        items: taskPage.value.items.map((item) => item.id === task.id ? task : item),
      }
    } finally {
      actionKey.value = null
    }
  }

  async function removeTask(taskId: number): Promise<void> {
    actionKey.value = `task:${taskId}`
    try {
      await deleteLearningTask(taskId)
    } finally {
      actionKey.value = null
    }
  }

  async function saveRecord(
    input: LearningRecordCreateInput | LearningRecordUpdateInput,
    recordId?: number,
  ): Promise<void> {
    await withSave(async () => {
      if (recordId) await updateLearningRecord(recordId, input)
      else await createLearningRecord(input as LearningRecordCreateInput)
    })
  }

  async function removeRecord(recordId: number): Promise<void> {
    actionKey.value = `record:${recordId}`
    try {
      await deleteLearningRecord(recordId)
    } finally {
      actionKey.value = null
    }
  }

  return {
    coursePage,
    planPage,
    taskPage,
    recordPage,
    loadingCourses,
    loadingPlans,
    loadingTasks,
    loadingRecords,
    saving,
    actionKey,
    courseError,
    planError,
    taskError,
    recordError,
    fetchCourses,
    fetchPlans,
    fetchTasks,
    fetchRecords,
    saveCourse,
    removeCourse,
    savePlan,
    removePlan,
    saveTask,
    completeTask,
    removeTask,
    saveRecord,
    removeRecord,
  }
})
