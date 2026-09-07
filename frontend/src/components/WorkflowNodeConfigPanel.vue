<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { WORKFLOW_NODE_TEMPLATES, getWorkflowNodeTone, isTeachingNode } from '@/domain/workflow'
import type { WorkflowCanvasNode, WorkflowCanvasNodeData } from '@/domain/workflow'

const props = defineProps<{
  node: WorkflowCanvasNode | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  update: [nodeId: string, data: WorkflowCanvasNodeData]
  delete: [nodeId: string]
  'pending-change': [pending: boolean]
}>()

const form = reactive({
  name: '',
  nodeType: 'requirements_analysis',
  instruction: '',
  expectedOutput: '',
  problem: '',
  studentCode: '',
})
const validationError = ref<string | null>(null)

watch(
  () => props.node,
  (node) => {
    form.name = node?.data.name ?? ''
    form.nodeType = node?.data.nodeType ?? 'requirements_analysis'
    form.instruction = typeof node?.data.config?.instruction === 'string'
      ? node.data.config.instruction
      : ''
    form.expectedOutput = typeof node?.data.config?.expected_output === 'string'
      ? node.data.config.expected_output
      : ''
    validationError.value = null
    form.problem = typeof node?.data.config?.problem === 'string' ? node.data.config.problem : ''
    form.studentCode = typeof node?.data.config?.student_code === 'string' ? node.data.config.student_code : ''
    emit('pending-change', false)
  },
  { immediate: true },
)

function save(): void {
  if (!props.node || props.disabled) return
  const name = form.name.trim()
  if (!name) {
    validationError.value = '请输入节点名称'
    return
  }
  validationError.value = null
  const config: NonNullable<WorkflowCanvasNodeData['config']> = {
    ...(props.node.data.config ?? {}),
    instruction: form.instruction.trim(),
    expected_output: form.expectedOutput.trim(),
  }
  if (isTeachingNode(form.nodeType)) {
    config.problem = form.problem.trim()
    config.student_code = form.studentCode || null
  } else {
    delete config.problem
    delete config.student_code
  }
  emit('update', props.node.id, {
    ...props.node.data,
    name,
    nodeType: form.nodeType,
    tone: getWorkflowNodeTone(form.nodeType),
    config,
  })
}
</script>

<template>
  <section class="workflow-node-config">
    <div class="workflow-panel-heading">
      <h2>节点配置</h2>
      <span>{{ node ? '已选择' : '未选择' }}</span>
    </div>
    <fieldset v-if="node" :disabled="disabled" class="workflow-node-config__form workflow-config-fields" @input="emit('pending-change', true)" @change="emit('pending-change', true)">
      <label class="field">
        节点名称
        <input v-model="form.name" maxlength="120" />
      </label>
      <label class="field">
        节点类型
        <select v-model="form.nodeType">
          <option v-for="template in WORKFLOW_NODE_TEMPLATES" :key="template.nodeType" :value="template.nodeType">
            {{ template.name }}
          </option>
        </select>
      </label>
      <label class="field">
        分析指令
        <textarea v-model="form.instruction" maxlength="1000" />
      </label>
      <label class="field">
        预期输出
        <textarea v-model="form.expectedOutput" maxlength="1000" />
      </label>
      <template v-if="isTeachingNode(form.nodeType)">
        <label class="field">
          练习题意（选填）
          <textarea v-model="form.problem" maxlength="5000" placeholder="留空时使用关联项目的说明和示例" />
        </label>
        <label class="field">
          {{ form.nodeType === 'exercise_hint' ? '我的代码（选填）' : '需要分析的代码（必填）' }}
          <textarea v-model="form.studentCode" class="workflow-code-input" maxlength="4000" spellcheck="false" placeholder="粘贴你自己的 Python 代码，保留缩进" />
        </label>
        <p class="muted-copy">代码将发送给已配置的 AI 进行分析，请勿填写密钥。答案评审不会执行代码或自动判题。</p>
      </template>
      <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
      <div class="workflow-node-config__actions">
        <button class="danger-command" type="button" @click="emit('delete', node.id)">删除节点</button>
        <button class="primary-command" type="button" @click="save">应用配置</button>
      </div>
    </fieldset>
    <div v-else class="workflow-panel-empty">选择画布中的节点后显示配置。</div>
  </section>
</template>
