<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import { difficultyLabels, formatProjectTime, getProjectStack, statusLabels } from '@/domain/projects'
import type { ProjectResponse } from '@/types/project'

const props = defineProps<{
  project: ProjectResponse
  imageUrl: string
  imageSrcset?: string
  featured?: boolean
}>()

const emit = defineEmits<{
  edit: [project: ProjectResponse]
  delete: [project: ProjectResponse]
}>()

const flipped = ref(false)
const flipTrigger = ref<HTMLButtonElement | null>(null)
const cardBack = ref<HTMLElement | null>(null)
const stack = computed(() => getProjectStack(props.project))
const description = computed(() => props.project.description || '这个项目还没有补充说明。')

async function toggleFlip(): Promise<void> {
  flipped.value = !flipped.value
  await nextTick()
  const target = flipped.value
    ? cardBack.value?.querySelector<HTMLAnchorElement>('a')
    : flipTrigger.value
  target?.focus({ preventScroll: true })
}
</script>

<template>
  <article
    class="project-flip-card"
    :class="{ 'is-featured': featured, 'is-flipped': flipped }"
  >
    <div class="project-flip-card__inner">
      <section class="project-flip-card__face project-flip-card__front" :inert="flipped">
        <img
          class="project-flip-card__cover"
          :src="imageUrl"
          :srcset="imageSrcset"
          sizes="(max-width: 760px) calc(100vw - 32px), (max-width: 1040px) 50vw, 33vw"
          :alt="`${project.name} 项目封面`"
          loading="lazy"
          width="800"
          height="420"
        />
        <div class="project-flip-card__content">
          <div class="project-flip-card__heading">
            <div class="project-flip-card__intro">
              <RouterLink class="project-flip-card__title" :title="project.name" :to="`/projects/${project.id}`">
                {{ project.name }}
              </RouterLink>
            </div>
            <span class="status-chip" :data-status="project.status">
              {{ statusLabels[project.status] }}
            </span>
          </div>

          <div class="tag-row" aria-label="技术栈">
            <span v-for="technology in stack.slice(0, 4)" :key="technology" class="tech-tag" :title="technology">
              {{ technology }}
            </span>
            <span v-if="stack.length === 0" class="tech-tag is-muted">待补充技术栈</span>
          </div>

          <p class="project-flip-card__description">{{ description }}</p>

          <div class="studio-card-progress">
            <span>项目进度 <strong>{{ project.progress }}%</strong></span>
            <div class="studio-progress" role="progressbar" :aria-label="`${project.name} 项目进度`" :aria-valuenow="project.progress" aria-valuemin="0" aria-valuemax="100"><span :style="{ transform: `scaleX(${project.progress / 100})` }" /></div>
          </div>

          <div class="project-flip-card__footer">
            <button class="text-command studio-front-edit" type="button" @click="emit('edit', project)">编辑</button>
            <RouterLink class="text-command" :to="`/projects/${project.id}`">查看详情</RouterLink>
            <button ref="flipTrigger" class="text-command" type="button" @click="toggleFlip">查看技术详情</button>
          </div>
        </div>
      </section>

      <section ref="cardBack" class="project-flip-card__face project-flip-card__back" :inert="!flipped">
        <div>
          <p class="project-flip-card__back-title" :title="project.name">{{ project.name }}</p>
          <dl class="project-facts">
            <div><dt>难度</dt><dd>{{ difficultyLabels[project.difficulty] }}</dd></div>
            <div><dt>更新时间</dt><dd>{{ formatProjectTime(project.updated_at) }}</dd></div>
            <div><dt>前端</dt><dd>{{ project.frontend || '未设置' }}</dd></div>
            <div><dt>后端</dt><dd>{{ project.backend || '未设置' }}</dd></div>
            <div><dt>数据库</dt><dd>{{ project.database || '未设置' }}</dd></div>
            <div><dt>框架</dt><dd>{{ project.framework || '未设置' }}</dd></div>
          </dl>
        </div>
        <div class="project-flip-card__actions">
          <RouterLink class="primary-command" :to="`/projects/${project.id}`">打开项目</RouterLink>
          <button class="secondary-command" type="button" @click="emit('edit', project)">编辑</button>
          <button class="danger-command" type="button" @click="emit('delete', project)">删除</button>
          <button class="text-command" type="button" @click="toggleFlip">返回封面</button>
        </div>
      </section>
    </div>
  </article>
</template>
