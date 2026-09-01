<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import { WORKFLOW_NODE_TEMPLATES, getWorkflowNodeTone } from '@/domain/workflow'
import type { WorkflowCanvasNode, WorkflowCanvasNodeData } from '@/domain/workflow'

const props = defineProps<{
  node: WorkflowCanvasNode | null
}>()

const emit = defineEmits<{
  update: [nodeId: string, data: WorkflowCanvasNodeData]
  delete: [nodeId: string]
}>()

const form = reactive({
  name: '',
  nodeType: 'requirements_analysis',
  instruction: '',
  expectedOutput: '',
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
  },
  { immediate: true },
)

function save(): void {
  if (!props.node) return
  const name = form.name.trim()
  if (!name) {
    validationError.value = '请输入节点名称'
    return
  }
  validationError.value = null
  emit('update', props.node.id, {
    ...props.node.data,
    name,
    nodeType: form.nodeType,
    tone: getWorkflowNodeTone(form.nodeType),
    config: {
      ...(props.node.data.config ?? {}),
      instruction: form.instruction.trim(),
      expected_output: form.expectedOutput.trim(),
    },
  })
}
</script>

<template>
  <section class="workflow-node-config">
    <div class="workflow-panel-heading">
      <h2>节点配置</h2>
      <span>{{ node ? '已选择' : '未选择' }}</span>
    </div>
    <div v-if="node" class="workflow-node-config__form">
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
        <textarea v-model="form.instruction" maxlength="5000" />
      </label>
      <label class="field">
        预期输出
        <textarea v-model="form.expectedOutput" maxlength="5000" />
      </label>
      <p v-if="validationError" class="field-error" role="alert">{{ validationError }}</p>
      <div class="workflow-node-config__actions">
        <button class="danger-command" type="button" @click="emit('delete', node.id)">删除节点</button>
        <button class="primary-command" type="button" @click="save">应用配置</button>
      </div>
    </div>
    <div v-else class="workflow-panel-empty">选择画布中的节点后显示配置。</div>
  </section>
</template>
