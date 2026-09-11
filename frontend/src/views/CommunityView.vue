<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { getApiErrorMessage } from '@/api/errors'
import CommunityProjectCard from '@/components/CommunityProjectCard.vue'
import LiquidTabs, { type LiquidTabOption } from '@/components/LiquidTabs.vue'
import NumberRoller from '@/components/NumberRoller.vue'
import { useCommunityStore } from '@/stores/community'
import type { CommunityProjectResponse } from '@/types/community'

const route = useRoute()
const router = useRouter()
const communityStore = useCommunityStore()
const pageNumber = ref(1)
const selectedTag = ref(typeof route.query.tag === 'string' ? route.query.tag : '')

const tagOptions = computed<LiquidTabOption[]>(() => [
  { value: '', label: `全部 ${communityStore.projectPage.total}` },
  ...communityStore.tags.map((tag) => ({
    value: tag.slug,
    label: `${tag.name} ${tag.project_count}`,
  })),
])

async function loadProjects(): Promise<void> {
  try {
    await communityStore.fetchProjects({
      page: pageNumber.value,
      pageSize: 12,
      ...(selectedTag.value ? { tag: selectedTag.value } : {}),
    })
  } catch {
    // Store 已保存可重试提示。
  }
}

async function changeTag(tag: string): Promise<void> {
  selectedTag.value = tag
  pageNumber.value = 1
  await router.replace({ name: 'community', query: tag ? { tag } : {} })
  await loadProjects()
}

async function changePage(nextPage: number): Promise<void> {
  pageNumber.value = nextPage
  await loadProjects()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function toggleLike(project: CommunityProjectResponse): Promise<void> {
  try {
    await communityStore.toggleLike(project)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '点赞状态更新失败，请重试'))
  }
}

async function toggleFavorite(project: CommunityProjectResponse): Promise<void> {
  try {
    await communityStore.toggleFavorite(project)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error, '收藏状态更新失败，请重试'))
  }
}

onMounted(() => {
  void loadProjects()
})
</script>

<template>
  <div class="page-shell community-page">
    <header class="community-header">
      <div>
        <p class="page-kicker">Campus Code Community</p>
        <h1>校园代码社区</h1>
        <p>发现同学们正在实践的真实项目，从技术标签进入共同兴趣。</p>
      </div>
      <div class="community-header__stat" aria-label="已发布项目数">
        <NumberRoller :value="communityStore.projectPage.total" />
        <span>个公开项目</span>
      </div>
      <div class="community-detail-actions">
        <RouterLink class="secondary-command" to="/community/governance">治理进度</RouterLink>
        <RouterLink class="primary-command" to="/projects">申请发布项目</RouterLink>
      </div>
    </header>

    <section class="community-filter" aria-labelledby="community-filter-title">
      <div class="panel-title-row">
        <h2 id="community-filter-title">按标签探索</h2>
        <span>发布较新的项目优先展示</span>
      </div>
      <div class="community-filter__scroll">
        <LiquidTabs
          :model-value="selectedTag"
          :options="tagOptions"
          ariaLabel="社区项目标签筛选"
          @update:model-value="changeTag"
        />
      </div>
    </section>

    <div v-if="communityStore.listError" class="inline-alert is-error" role="alert">
      <span>{{ communityStore.listError }}</span>
      <button type="button" @click="loadProjects">重试</button>
    </div>

    <div v-if="communityStore.listLoading" class="community-grid-loading" aria-label="社区项目加载中">
      <span v-for="index in 6" :key="index" />
    </div>

    <section
      v-else-if="communityStore.projectPage.items.length > 0"
      class="community-grid"
      aria-label="社区项目列表"
    >
      <CommunityProjectCard
        v-for="(project, index) in communityStore.projectPage.items"
        :key="project.id"
        :project="project"
        :index="index"
        :action-disabled="communityStore.actionLoading"
        @like="toggleLike"
        @favorite="toggleFavorite"
      />
    </section>

    <section v-else class="empty-state wide-empty-state">
      <h2>{{ selectedTag ? '这个标签下还没有项目' : '社区正在等待第一个项目' }}</h2>
      <p>{{ selectedTag ? '切换其他标签继续浏览。' : '从项目库提交发布申请，人工审核通过后才会出现在这里。' }}</p>
      <RouterLink class="primary-command" to="/projects">前往项目库</RouterLink>
    </section>

    <nav v-if="communityStore.projectPage.total_pages > 1" class="pagination" aria-label="社区项目分页">
      <button
        type="button"
        :disabled="communityStore.projectPage.page <= 1 || communityStore.listLoading"
        @click="changePage(communityStore.projectPage.page - 1)"
      >
        上一页
      </button>
      <span>第 {{ communityStore.projectPage.page }} / {{ communityStore.projectPage.total_pages }} 页</span>
      <button
        type="button"
        :disabled="communityStore.projectPage.page >= communityStore.projectPage.total_pages || communityStore.listLoading"
        @click="changePage(communityStore.projectPage.page + 1)"
      >
        下一页
      </button>
    </nav>
  </div>
</template>
