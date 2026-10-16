<script setup lang="ts">
import home from '@/assets/campus-studio/icons/home.svg'
import project from '@/assets/campus-studio/icons/project.svg'
import learning from '@/assets/campus-studio/icons/learning.svg'
import data from '@/assets/campus-studio/icons/data.svg'
import more from '@/assets/campus-studio/icons/more.svg'
import search from '@/assets/campus-studio/icons/search.svg'
import arrow from '@/assets/campus-studio/icons/arrow.svg'
import plus from '@/assets/campus-studio/icons/plus.svg'
import close from '@/assets/campus-studio/icons/close.svg'
import community from '@/assets/campus-studio/icons/community.svg'
import workspace from '@/assets/campus-studio/icons/workspace.svg'
import workflow from '@/assets/campus-studio/icons/workflow.svg'
import profile from '@/assets/campus-studio/icons/profile.svg'

const icons = { home, project, learning, data, more, search, arrow, plus, close, community, workspace, workflow, profile }
defineProps<{ name: keyof typeof icons }>()
</script>

<template>
  <img class="studio-icon" :src="icons[name]" alt="" aria-hidden="true" />
</template>
