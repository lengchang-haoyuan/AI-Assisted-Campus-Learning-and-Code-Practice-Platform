<script setup lang="ts">
import { computed, ref } from 'vue'

import { getProjectCover } from '@/assets/projectCovers'
import NumberRoller from '@/components/NumberRoller.vue'
import { difficultyLabels, formatProjectTime, statusLabels } from '@/domain/projects'
import type { CommunityProjectResponse } from '@/types/community'

const props = defineProps<{
  project: CommunityProjectResponse
  index: number
  actionDisabled?: boolean
}>()

const emit = defineEmits<{
  like: [project: CommunityProjectResponse]
  favorite: [project: CommunityProjectResponse]
}>()

const flipped = ref(false)
const stack = computed(() =>
  [props.project.language, props.project.framework, props.project.frontend, props.project.backend]
    .filter((value): value is string => Boolean(value))
    .filter((value, index, values) => values.indexOf(value) === index),
)

function toggleFlip(): void {
  flipped.value = !flipped.value
}
</script>

<template>
  <article class="community-card" :class="{ 'is-flipped': flipped }">
    <div class="community-card__inner">
      <section class="community-card__face community-card__front" :inert="flipped">
        <img
          class="community-card__cover"
          :src="getProjectCover(project.id, index)"
          :alt="`${project.name} 项目封面`"
        />
        <div class="community-card__body">
          <div class="community-card__meta">
            <span class="status-chip" :data-status="project.status">
              {{ statusLabels[project.status] }}
            </span>
            <span v-if="project.publication_kind === 'practice_template'" class="tech-tag">实践模板</span>
            <span v-else-if="project.publication_status === 'legacy_review_required'" class="tech-tag">待补审</span>
            <span>由 {{ project.owner.username }} 发布</span>
          </div>
          <RouterLink class="community-card__title" :to="`/community/projects/${project.id}`">
            {{ project.name }}
          </RouterLink>
          <p>{{ project.description || '发布者暂未补充项目说明。' }}</p>
          <div class="tag-row" aria-label="项目标签">
            <span v-for="tag in project.tags.slice(0, 3)" :key="tag.id" class="tech-tag">
              {{ tag.name }}
            </span>
            <span v-if="project.tags.length === 0" class="tech-tag is-muted">未添加标签</span>
          </div>
        </div>
        <footer class="community-card__footer">
          <span><NumberRoller :value="project.view_count" /> 浏览</span>
          <span><NumberRoller :value="project.like_count" /> 赞</span>
          <span><NumberRoller :value="project.comment_count" /> 评论</span>
          <button class="text-command" type="button" @click="toggleFlip">技术详情</button>
        </footer>
      </section>

      <section class="community-card__face community-card__back" :inert="!flipped">
        <div>
          <p class="community-card__eyebrow">项目技术铭牌</p>
          <h2>{{ project.name }}</h2>
          <dl class="project-facts">
            <div><dt>难度</dt><dd>{{ difficultyLabels[project.difficulty] }}</dd></div>
            <div><dt>语言</dt><dd>{{ project.language || '未设置' }}</dd></div>
            <div><dt>框架</dt><dd>{{ project.framework || '未设置' }}</dd></div>
            <div><dt>最近更新</dt><dd>{{ formatProjectTime(project.updated_at) }}</dd></div>
          </dl>
          <div class="tag-row" aria-label="技术栈">
            <span v-for="technology in stack" :key="technology" class="tech-tag">
              {{ technology }}
            </span>
          </div>
        </div>
        <div class="community-card__actions">
          <RouterLink class="primary-command compact-command" :to="`/community/projects/${project.id}`">
            查看项目
          </RouterLink>
          <button
            class="secondary-command compact-command"
            type="button"
            :disabled="actionDisabled"
            :aria-pressed="project.liked"
            @click="emit('like', project)"
          >
            {{ project.liked ? '已点赞' : '点赞' }} · {{ project.like_count }}
          </button>
          <button
            class="secondary-command compact-command"
            type="button"
            :disabled="actionDisabled"
            :aria-pressed="project.favorited"
            @click="emit('favorite', project)"
          >
            {{ project.favorited ? '已收藏' : '收藏' }} · {{ project.favorite_count }}
          </button>
          <button class="text-command" type="button" @click="toggleFlip">返回封面</button>
        </div>
      </section>
    </div>
  </article>
</template>
