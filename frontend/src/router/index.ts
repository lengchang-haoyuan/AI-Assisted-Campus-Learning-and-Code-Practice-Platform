import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { getCampusMe } from '@/api/campus'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('@/views/ResetPasswordView.vue'),
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'community',
          name: 'community',
          component: () => import('@/views/CommunityView.vue'),
        },
        {
          path: 'community/projects/:id',
          name: 'community-project-detail',
          component: () => import('@/views/CommunityProjectDetailView.vue'),
        },
        {
          path: 'projects',
          name: 'projects',
          component: () => import('@/views/ProjectsView.vue'),
        },
        {
          path: 'projects/:id/ai',
          name: 'project-ai-workspace',
          component: () => import('@/views/ProjectAIWorkspaceView.vue'),
        },
        {
          path: 'projects/:id',
          name: 'project-detail',
          component: () => import('@/views/ProjectDetailView.vue'),
        },
        {
          path: 'workspace/dashboard',
          name: 'workspace-dashboard',
          component: () => import('@/views/WorkspaceDashboardView.vue'),
        },
        {
          path: 'workspace/tasks',
          name: 'workspace-tasks',
          component: () => import('@/views/WorkspaceTasksView.vue'),
        },
        {
          path: 'workspace/projects',
          name: 'workspace-projects',
          component: () => import('@/views/WorkspaceProjectsView.vue'),
        },
        {
          path: 'workspace/projects/:id',
          name: 'workspace-project-detail',
          component: () => import('@/views/WorkspaceProjectDetailView.vue'),
        },
        {
          path: 'workspace/records',
          name: 'workspace-records',
          component: () => import('@/views/WorkspaceRecordsView.vue'),
        },
        {
          path: 'learning',
          name: 'learning-overview',
          component: () => import('@/views/LearningOverviewView.vue'),
        },
        {
          path: 'learning/tasks',
          name: 'learning-tasks',
          component: () => import('@/views/LearningTasksView.vue'),
        },
        {
          path: 'learning/records',
          name: 'learning-records',
          component: () => import('@/views/LearningRecordsView.vue'),
        },
        {
          path: 'workflows',
          name: 'workflows',
          component: () => import('@/views/WorkflowsView.vue'),
        },
        {
          path: 'workflows/:id',
          name: 'workflow-editor',
          component: () => import('@/views/WorkflowEditorView.vue'),
        },
        {
          path: 'analytics',
          name: 'analytics',
          component: () => import('@/views/AnalyticsView.vue'),
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
        },
        {
          path: 'campus/join',
          name: 'campus-join',
          component: () => import('@/views/CampusJoinView.vue'),
        },
        {
          path: 'campus/classes',
          name: 'campus-classes',
          component: () => import('@/views/ClassroomsView.vue'),
        },
        {
          path: 'campus/classes/:classId',
          name: 'campus-class-detail',
          component: () => import('@/views/ClassroomDetailView.vue'),
        },
        {
          path: 'campus/assignments/:assignmentId',
          name: 'campus-assignment-detail',
          component: () => import('@/views/TeachingAssignmentDetailView.vue'),
        },
        {
          path: 'campus/submissions',
          name: 'campus-submissions',
          component: () => import('@/views/SubmissionsView.vue'),
        },
        {
          path: 'campus/submissions/:submissionId',
          name: 'campus-submission-detail',
          component: () => import('@/views/SubmissionDetailView.vue'),
        },
        {
          path: 'notifications',
          name: 'notifications',
          component: () => import('@/views/NotificationsView.vue'),
        },
        {
          path: 'campus/admin/accounts',
          name: 'campus-admin',
          component: () => import('@/views/CampusAdminView.vue'),
          meta: { campusAdmin: true },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia)
  if (!authStore.initialized) await authStore.restoreSession()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && authStore.isLoggedIn) return { name: 'home' }
  if (to.meta.campusAdmin && authStore.isLoggedIn) {
    const membership = (await getCampusMe()).membership
    if (membership?.role !== 'administrator' || membership.status !== 'active') {
      return { name: 'campus-join' }
    }
  }
  return true
})

export default router
