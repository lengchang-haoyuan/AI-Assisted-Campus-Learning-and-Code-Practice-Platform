<script setup lang="ts">
import { computed, ref } from 'vue'

import { difficultyLabels, formatProjectTime, getProjectStack, statusLabels } from '@/domain/projects'
import type { ProjectResponse } from '@/types/project'

const props = defineProps<{
  project: ProjectResponse
  imageUrl: string
  featured?: boolean
}>()

const emit = defineEmits<{
  edit: [project: ProjectResponse]
  delete: [project: ProjectResponse]
}>()

const flipped = ref(false)
const stack = computed(() => getProjectStack(props.project))
const description = computed(() => props.project.description || '这个项目还没有补充说明。')

function toggleFlip(): void {
  flipped.value = !flipped.value
}
</script>

<template>
  <article
    class="project-flip-card"
    :class="{ 'is-featured': featured, 'is-flipped': flipped }"
  >
    <div class="project-flip-card__inner">
      <section class="project-flip-card__face project-flip-card__front" :inert="flipped">
        <img class="project-flip-card__cover" :src="imageUrl" :alt="`${project.name} 项目封面`" />
        <div class="project-flip-card__content">
          <div class="project-flip-card__heading">
            <div>
              <RouterLink class="project-flip-card__title" :to="`/projects/${project.id}`">
                {{ project.name }}
              </RouterLink>
              <p>{{ description }}</p>
            </div>
            <span class="status-chip" :data-status="project.status">
              {{ statusLabels[project.status] }}
            </span>
          </div>

          <div class="tag-row" aria-label="技术栈">
            <span v-for="technology in stack.slice(0, 4)" :key="technology" class="tech-tag">
              {{ technology }}
            </span>
            <span v-if="stack.length === 0" class="tech-tag is-muted">待补充技术栈</span>
          </div>

          <div class="project-flip-card__footer">
            <span>{{ difficultyLabels[project.difficulty] }}</span>
            <span>更新于 {{ formatProjectTime(project.updated_at) }}</span>
            <button class="text-command" type="button" @click="toggleFlip">查看技术详情</button>
          </div>
        </div>
      </section>

      <section class="project-flip-card__face project-flip-card__back" :inert="!flipped">
        <div>
          <p class="project-flip-card__back-title">{{ project.name }}</p>
          <dl class="project-facts">
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
