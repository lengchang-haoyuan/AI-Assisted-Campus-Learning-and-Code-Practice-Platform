<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import { reportCommunityContent } from '@/api/community'
import { getProjectCover } from '@/assets/projectCovers'
import NumberRoller from '@/components/NumberRoller.vue'
import { difficultyLabels, formatProjectTime, statusLabels } from '@/domain/projects'
import { useCommunityStore } from '@/stores/community'
import { useAuthStore } from '@/stores/auth'
import type { CommentResponse } from '@/types/community'

const route = useRoute()
const communityStore = useCommunityStore()
const authStore = useAuthStore()
const commentContent = ref('')
const commentError = ref<string | null>(null)
const reportKeys = new Map<string, string>()

const projectId = computed(() => {
  const value = Number(route.params.id)
  return Number.isInteger(value) && value > 0 ? value : null
})
const project = computed(() => communityStore.currentProject)
const stack = computed(() => {
  if (!project.value) return []
  return [
    project.value.language,
    project.value.framework,
    project.value.frontend,
    project.value.backend,
    project.value.database,
  ]
    .filter((value): value is string => Boolean(value))
    .filter((value, index, values) => values.indexOf(value) === index)
})

async function loadProject(): Promise<void> {
  if (projectId.value === null) return
  try {
    await communityStore.fetchProject(projectId.value)
    await Promise.all([
      communityStore.countView(projectId.value),
      communityStore.fetchComments(projectId.value),
    ])
  } catch {
    // Store 已保存对应错误状态。
  }
}

async function toggleLike(): Promise<void> {
  if (!project.value) return
  try {
    await communityStore.toggleLike(project.value)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '点赞状态更新失败，请重试'))
  }
}

async function toggleFavorite(): Promise<void> {
  if (!project.value) return
  try {
    await communityStore.toggleFavorite(project.value)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '收藏状态更新失败，请重试'))
  }
}

async function submitComment(): Promise<void> {
  if (projectId.value === null) return
  const content = commentContent.value.trim()
  commentError.value = null
  if (!content) {
    commentError.value = '请输入评论内容'
    return
  }
  if (content.length > 2000) {
    commentError.value = '评论不能超过 2000 个字符'
    return
  }
  try {
    await communityStore.addComment(projectId.value, content)
    commentContent.value = ''
    ElMessage.success('评论已发布')
  } catch (error: unknown) {
    commentError.value = getApiErrorMessage(error, '评论发布失败，请重试')
  }
}

async function removeComment(comment: CommentResponse): Promise<void> {
  try {
    await ElMessageBox.confirm('删除这条评论后无法恢复。', '确认删除评论', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
    await communityStore.removeComment(comment.id)
    ElMessage.success('评论已删除')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '评论删除失败，请重试'))
  }
}

async function reportContent(targetType: 'project' | 'comment', targetId: number): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      '请填写具体举报原因（3至500个字符）。举报人身份不会向内容作者公开。',
      targetType === 'project' ? '举报项目' : '举报评论',
      {
        confirmButtonText: '提交举报',
        cancelButtonText: '取消',
        inputValidator: (text) => {
          const length = text.trim().length
          return (length >= 3 && length <= 500) || '请填写 3 至 500 个字符'
        },
      },
    )
    const reason = value.trim()
    const fingerprint = `${targetType}:${targetId}:${reason}`
    const key = reportKeys.get(fingerprint)
      ?? (typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID().replaceAll('-', '')
        : `report_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`)
    reportKeys.set(fingerprint, key)
    await reportCommunityContent(targetType, targetId, reason, key)
    reportKeys.delete(fingerprint)
    ElMessage.success('举报已提交，可在“治理进度”查询结果')
  } catch (error: unknown) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '举报提交失败；重试相同内容时不会重复建案'))
  }
}

async function changeCommentPage(nextPage: number): Promise<void> {
  if (projectId.value === null) return
  try {
    await communityStore.fetchComments(projectId.value, nextPage)
  } catch {
    // Store 已保存可重试提示。
  }
}

onMounted(() => {
  void loadProject()
})

onBeforeUnmount(() => {
  communityStore.clearDetail()
})
</script>

<template>
  <div class="page-shell community-detail-page">
    <RouterLink class="back-link" to="/community">返回校园代码社区</RouterLink>

    <div v-if="projectId === null" class="inline-alert is-error" role="alert">项目地址无效。</div>

    <div v-else-if="communityStore.detailLoading" class="detail-skeleton" aria-label="社区项目加载中">
      <span /><span /><span />
    </div>

    <div v-else-if="communityStore.detailError" class="inline-alert is-error" role="alert">
      <span>{{ communityStore.detailError }}</span>
      <button type="button" @click="loadProject">重试</button>
    </div>

    <template v-else-if="project">
      <header class="community-detail-header">
        <div>
          <div class="tag-row">
            <span class="status-chip" :data-status="project.status">{{ statusLabels[project.status] }}</span>
            <span class="tech-tag">{{ difficultyLabels[project.difficulty] }}</span>
            <span v-if="project.publication_kind === 'practice_template'" class="tech-tag">教学实践模板</span>
            <span v-if="project.publication_status === 'legacy_review_required'" class="tech-tag">历史内容待补审</span>
          </div>
          <h1>{{ project.name }}</h1>
          <p>{{ project.description || '发布者暂未补充项目说明。' }}</p>
          <div class="community-owner-line">
            <span class="avatar is-small" aria-hidden="true">{{ project.owner.username.slice(0, 1).toUpperCase() }}</span>
            <span>{{ project.owner.username }}</span>
            <span>发布于 {{ formatProjectTime(project.published_at) }}</span>
          </div>
        </div>
        <div class="community-detail-actions">
          <button
            class="secondary-command"
            type="button"
            :disabled="communityStore.actionLoading"
            :aria-pressed="project.liked"
            @click="toggleLike"
          >
            {{ project.liked ? '已点赞' : '点赞项目' }}
          </button>
          <button
            class="secondary-command"
            type="button"
            :disabled="communityStore.actionLoading"
            :aria-pressed="project.favorited"
            @click="toggleFavorite"
          >
            {{ project.favorited ? '已收藏' : '收藏项目' }}
          </button>
          <button
            v-if="project.owner.id !== authStore.currentUser?.id"
            class="text-command danger-text-command"
            type="button"
            :disabled="communityStore.actionLoading"
            @click="reportContent('project', project.id)"
          >
            举报项目
          </button>
        </div>
      </header>

      <section class="community-metrics" aria-label="项目互动数据">
        <div><NumberRoller :value="project.view_count" /><span>浏览</span></div>
        <div><NumberRoller :value="project.like_count" /><span>点赞</span></div>
        <div><NumberRoller :value="project.favorite_count" /><span>收藏</span></div>
        <div><NumberRoller :value="project.comment_count" /><span>评论</span></div>
      </section>

      <div class="community-detail-grid">
        <section class="community-project-story">
          <img :src="getProjectCover(project.id)" :alt="`${project.name} 项目封面`" />
          <div>
            <h2>项目说明</h2>
            <p>{{ project.description || '发布者暂未补充项目说明。' }}</p>
          </div>
        </section>

        <aside class="community-tech-panel">
          <h2>技术铭牌</h2>
          <div class="tag-row">
            <span v-for="tag in project.tags" :key="tag.id" class="tech-tag">{{ tag.name }}</span>
            <span v-if="project.tags.length === 0" class="tech-tag is-muted">未添加标签</span>
          </div>
          <dl class="detail-facts">
            <div><dt>语言</dt><dd>{{ project.language || '未设置' }}</dd></div>
            <div><dt>框架</dt><dd>{{ project.framework || '未设置' }}</dd></div>
            <div><dt>前端</dt><dd>{{ project.frontend || '未设置' }}</dd></div>
            <div><dt>后端</dt><dd>{{ project.backend || '未设置' }}</dd></div>
            <div><dt>数据库</dt><dd>{{ project.database || '未设置' }}</dd></div>
          </dl>
          <div v-if="stack.length" class="code-preview" aria-label="技术栈摘要">
            <span v-for="technology in stack" :key="technology">{{ technology }}</span>
          </div>
          <dl class="detail-facts community-declarations">
            <div><dt>署名</dt><dd>{{ project.attribution || '未填写' }}</dd></div>
            <div><dt>来源或许可</dt><dd>{{ project.source_license_statement || '历史内容待补充' }}</dd></div>
            <div><dt>AI 辅助声明</dt><dd>{{ project.ai_assistance_statement || '历史内容待补充' }}</dd></div>
            <div v-if="project.publication_kind === 'practice_template'"><dt>人工审阅</dt><dd>{{ project.human_review_statement || '未填写' }}</dd></div>
          </dl>
        </aside>
      </div>

      <section class="comment-board" aria-labelledby="comment-board-title">
        <div class="panel-title-row">
          <h2 id="comment-board-title">项目讨论</h2>
          <span>{{ communityStore.commentPage.total }} 条评论</span>
        </div>

        <form class="comment-form" @submit.prevent="submitComment">
          <label class="field">
            <span>写下你的建议或问题</span>
            <textarea v-model="commentContent" rows="3" maxlength="2000" placeholder="围绕实现、学习思路或改进方向展开讨论" />
            <small>{{ commentContent.length }} / 2000</small>
          </label>
          <div v-if="commentError" class="inline-alert is-error" role="alert">{{ commentError }}</div>
          <button class="primary-command" type="submit" :disabled="communityStore.actionLoading">
            {{ communityStore.actionLoading ? '正在发布…' : '发表评论' }}
          </button>
        </form>

        <div v-if="communityStore.commentsError" class="inline-alert is-error" role="alert">
          <span>{{ communityStore.commentsError }}</span>
          <button type="button" @click="changeCommentPage(communityStore.commentPage.page)">重试</button>
        </div>
        <div v-if="communityStore.commentsLoading" class="comment-skeleton" aria-label="评论加载中">
          <span v-for="index in 3" :key="index" />
        </div>
        <ol v-else-if="communityStore.commentPage.items.length" class="comment-list">
          <li v-for="comment in communityStore.commentPage.items" :key="comment.id">
            <span class="avatar is-small" aria-hidden="true">{{ comment.author.username.slice(0, 1).toUpperCase() }}</span>
            <div>
              <div class="comment-list__meta">
                <strong>{{ comment.author.username }}</strong>
                <time :datetime="comment.created_at">{{ formatProjectTime(comment.created_at) }}</time>
              </div>
              <p>{{ comment.content }}</p>
            </div>
            <button
              v-if="comment.can_delete"
              class="text-command danger-text-command"
              type="button"
              :disabled="communityStore.actionLoading"
              @click="removeComment(comment)"
            >
              删除
            </button>
            <button
              v-else-if="comment.can_report"
              class="text-command danger-text-command"
              type="button"
              :disabled="communityStore.actionLoading"
              @click="reportContent('comment', comment.id)"
            >
              举报
            </button>
          </li>
        </ol>
        <div v-else class="comment-empty">还没有评论，成为第一个参与讨论的人。</div>

        <nav v-if="communityStore.commentPage.total_pages > 1" class="pagination" aria-label="评论分页">
          <button
            type="button"
            :disabled="communityStore.commentPage.page <= 1 || communityStore.commentsLoading"
            @click="changeCommentPage(communityStore.commentPage.page - 1)"
          >
            上一页
          </button>
          <span>第 {{ communityStore.commentPage.page }} / {{ communityStore.commentPage.total_pages }} 页</span>
          <button
            type="button"
            :disabled="communityStore.commentPage.page >= communityStore.commentPage.total_pages || communityStore.commentsLoading"
            @click="changeCommentPage(communityStore.commentPage.page + 1)"
          >
            下一页
          </button>
        </nav>
      </section>
    </template>
  </div>
</template>
