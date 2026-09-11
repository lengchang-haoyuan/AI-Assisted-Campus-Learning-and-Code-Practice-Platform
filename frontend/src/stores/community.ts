import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  createProjectComment as createProjectCommentRequest,
  deleteComment as deleteCommentRequest,
  getCommunityProject,
  listCommunityProjects,
  listCommunityTags,
  listProjectComments,
  recordProjectView,
  setProjectFavorite,
  setProjectLike,
} from '@/api/community'
import { getApiErrorMessage } from '@/api/errors'
import type {
  CommentListResponse,
  CommentResponse,
  CommunityProjectListQuery,
  CommunityProjectListResponse,
  CommunityProjectResponse,
  TagSummaryResponse,
} from '@/types/community'

const EMPTY_PROJECT_PAGE: CommunityProjectListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 12,
  total_pages: 0,
}

const EMPTY_COMMENT_PAGE: CommentListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
  total_pages: 0,
}

export const useCommunityStore = defineStore('community', () => {
  const projectPage = ref<CommunityProjectListResponse>({ ...EMPTY_PROJECT_PAGE })
  const commentPage = ref<CommentListResponse>({ ...EMPTY_COMMENT_PAGE })
  const currentProject = ref<CommunityProjectResponse | null>(null)
  const tags = ref<TagSummaryResponse[]>([])
  const listLoading = ref(false)
  const detailLoading = ref(false)
  const commentsLoading = ref(false)
  const actionLoading = ref(false)
  const listError = ref<string | null>(null)
  const detailError = ref<string | null>(null)
  const commentsError = ref<string | null>(null)
  let listRequestSequence = 0
  let detailRequestSequence = 0
  let commentRequestSequence = 0

  function replaceProject(nextProject: CommunityProjectResponse): void {
    currentProject.value = nextProject
    const index = projectPage.value.items.findIndex((project) => project.id === nextProject.id)
    if (index >= 0) projectPage.value.items[index] = nextProject
  }

  async function fetchProjects(query: CommunityProjectListQuery): Promise<void> {
    const sequence = ++listRequestSequence
    listLoading.value = true
    listError.value = null
    try {
      const [pageResult, tagResult] = await Promise.all([
        listCommunityProjects(query),
        listCommunityTags(),
      ])
      if (sequence === listRequestSequence) {
        projectPage.value = pageResult
        tags.value = tagResult
      }
    } catch (error: unknown) {
      if (sequence === listRequestSequence) {
        listError.value = getApiErrorMessage(error, '社区项目加载失败，请重试')
      }
      throw error
    } finally {
      if (sequence === listRequestSequence) listLoading.value = false
    }
  }

  async function fetchProject(projectId: number): Promise<CommunityProjectResponse> {
    const sequence = ++detailRequestSequence
    detailLoading.value = true
    detailError.value = null
    try {
      const project = await getCommunityProject(projectId)
      if (sequence === detailRequestSequence) replaceProject(project)
      return project
    } catch (error: unknown) {
      if (sequence === detailRequestSequence) {
        currentProject.value = null
        detailError.value = getApiErrorMessage(error, '社区项目详情加载失败，请重试')
      }
      throw error
    } finally {
      if (sequence === detailRequestSequence) detailLoading.value = false
    }
  }

  async function fetchComments(projectId: number, page = 1): Promise<void> {
    const sequence = ++commentRequestSequence
    commentsLoading.value = true
    commentsError.value = null
    try {
      const result = await listProjectComments(projectId, page, 20)
      if (sequence === commentRequestSequence) commentPage.value = result
    } catch (error: unknown) {
      if (sequence === commentRequestSequence) {
        commentsError.value = getApiErrorMessage(error, '评论加载失败，请重试')
      }
      throw error
    } finally {
      if (sequence === commentRequestSequence) commentsLoading.value = false
    }
  }

  async function addComment(projectId: number, content: string): Promise<CommentResponse> {
    actionLoading.value = true
    try {
      const comment = await createProjectCommentRequest(projectId, content)
      commentPage.value = {
        ...commentPage.value,
        items: [...commentPage.value.items, comment],
        total: commentPage.value.total + 1,
      }
      if (currentProject.value?.id === projectId) currentProject.value.comment_count += 1
      return comment
    } finally {
      actionLoading.value = false
    }
  }

  async function removeComment(commentId: number): Promise<void> {
    actionLoading.value = true
    try {
      await deleteCommentRequest(commentId)
      commentPage.value = {
        ...commentPage.value,
        items: commentPage.value.items.filter((comment) => comment.id !== commentId),
        total: Math.max(0, commentPage.value.total - 1),
      }
      if (currentProject.value) {
        currentProject.value.comment_count = Math.max(0, currentProject.value.comment_count - 1)
      }
    } finally {
      actionLoading.value = false
    }
  }

  async function toggleLike(project: CommunityProjectResponse): Promise<void> {
    actionLoading.value = true
    try {
      const result = await setProjectLike(project.id, !project.liked)
      replaceProject({ ...project, liked: result.active, like_count: result.count })
    } finally {
      actionLoading.value = false
    }
  }

  async function toggleFavorite(project: CommunityProjectResponse): Promise<void> {
    actionLoading.value = true
    try {
      const result = await setProjectFavorite(project.id, !project.favorited)
      replaceProject({ ...project, favorited: result.active, favorite_count: result.count })
    } finally {
      actionLoading.value = false
    }
  }

  async function countView(projectId: number): Promise<void> {
    const result = await recordProjectView(projectId)
    if (currentProject.value?.id === projectId) currentProject.value.view_count = result.view_count
  }

  function clearDetail(): void {
    currentProject.value = null
    commentPage.value = { ...EMPTY_COMMENT_PAGE }
    detailError.value = null
    commentsError.value = null
  }

  return {
    projectPage,
    commentPage,
    currentProject,
    tags,
    listLoading,
    detailLoading,
    commentsLoading,
    actionLoading,
    listError,
    detailError,
    commentsError,
    fetchProjects,
    fetchProject,
    fetchComments,
    addComment,
    removeComment,
    toggleLike,
    toggleFavorite,
    countView,
    clearDetail,
  }
})
