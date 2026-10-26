<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePracticeWorkbench } from '@/composables/usePracticeWorkbench'
import { availableActions, canSubmit, isGuidance, parseSubmission, PRACTICE_STATUS, PRACTICE_TEMPLATE } from '@/domain/practice'
import PracticeFeedbackPanel from '@/components/PracticeFeedbackPanel.vue'
import WorkflowNodeResultContent from '@/components/WorkflowNodeResultContent.vue'
import type { PracticeAction } from '@/types/practice'
import '@/styles/practice-workbench.css'

const route = useRoute(), router = useRouter(), auth = useAuthStore()
const w = usePracticeWorkbench()
const { project, context, session, history, page, loading, localBusy, modelBusy, error, notice, selectedAttemptId, selectedAttempt, selectedCurrent } = w
const code = ref(''), output = ref(''), selfStatement = ref('unset'), editing = ref(false), reviewed = ref(false)
const formError = ref<string | null>(null), copyNotice = ref<string | null>(null)
const dirty = computed(() => editing.value && (code.value.trim().length > 0 || output.value.trim().length > 0))
const actions = computed(() => session.value ? availableActions(session.value) : [])
const busy = computed(() => localBusy.value || modelBusy.value || loading.value)
const oldContext = computed(() => session.value && context.value && session.value.context_version !== context.value.version)
const guidance = computed(() => {
  const value = session.value?.current_step_key === 'understand' ? session.value.outputs.understand : selectedCurrent.value ? session.value?.active_result : null
  return isGuidance(value) ? { result_type: 'practice_guidance', summary: value.summary, steps: value.guidance, suggested_tests: value.checks } : null
})
const fakeAdvice = computed(() => Boolean(session.value?.model_request?.provider === 'fake' && selectedAttempt.value?.feedback.ai_static_review?.ai_request_id === session.value.model_request.id))
const canCreate = computed(() => context.value && !context.value.is_stale && !busy.value && !dirty.value)
function time(value: string): string { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function resetEditor(): void { code.value = ''; output.value = ''; selfStatement.value = 'unset'; editing.value = false; reviewed.value = false; formError.value = copyNotice.value = null }
watch(() => [route.params.id, route.query.session, auth.token], () => {
  resetEditor()
  void w.load(auth.token ? Number(route.params.id) : 0, typeof route.query.session === 'string' ? route.query.session : undefined)
}, { immediate: true })
watch(() => session.value?.current_attempt?.id, () => { reviewed.value = false })
watch(selectedAttemptId, () => { reviewed.value = false; copyNotice.value = null })
function allowLeave(): boolean { return !dirty.value || window.confirm('这份代码草稿尚未提交。离开会丢弃本页草稿，已保存的提交和会话会保留。继续离开？') }
onBeforeRouteLeave(allowLeave)
onBeforeRouteUpdate((to, from) => (to.params.id === from.params.id && to.query.session === from.query.session) || allowLeave())
async function create(): Promise<void> {
  const value = await w.create()
  if (value) await router.replace({ query: { session: value.id } })
}
function edit(): void {
  const current = session.value?.current_attempt
  code.value = current?.code ?? ''
  output.value = current ? JSON.stringify(current.declared_output, null, 2) : ''
  selfStatement.value = current?.self_statement === true ? 'true' : current?.self_statement === false ? 'false' : 'unset'
  editing.value = true; reviewed.value = false; formError.value = null
}
async function submit(): Promise<void> {
  formError.value = null
  try {
    const declared = parseSubmission(code.value, output.value)
    if (await w.submit({ code: code.value, declared_output: declared, self_statement: selfStatement.value === 'unset' ? null : selfStatement.value === 'true' })) resetEditor()
  } catch (cause: unknown) { formError.value = cause instanceof Error ? cause.message : '提交材料格式无效。' }
}
async function act(kind: PracticeAction): Promise<void> {
  if (kind === 'confirm' && !reviewed.value) return
  if (['start', 'hint', 'explain', 'review', 'continue'].includes(kind) && !window.confirm('这会明确请求一次 AI 帮助，并可能产生模型用量。继续？')) return
  await w.action(kind)
  if (kind === 'confirm') reviewed.value = false
}
async function copy(): Promise<void> {
  const item = selectedAttempt.value
  if (!item) return
  try { await navigator.clipboard.writeText(item.code); if (selectedAttempt.value?.id === item.id) copyNotice.value = `已复制提交 ${item.attempt_no} 的代码。` }
  catch { copyNotice.value = '复制失败，请在代码区域选择文本后手动复制。' }
}
</script>

<template>
  <section class="page-shell practice-page">
    <RouterLink class="back-link" :to="`/projects/${route.params.id}/ai`">返回项目准备</RouterLink>
    <header class="page-header"><div><h1>{{ project?.name ?? '项目' }} · 实践工作台</h1><p>读任务、提交实现，按需获取建议，再由本人审阅结束。</p></div><RouterLink class="secondary-command" to="/workflows">高级工作流与历史</RouterLink></header>
    <div v-if="loading && !project" class="practice-loading" role="status">正在载入本人实践记录…</div>
    <p v-if="error" class="inline-alert is-error" role="alert">{{ error }}<button type="button" class="text-command" @click="w.load(Number(route.params.id), typeof route.query.session === 'string' ? route.query.session : undefined)">重新载入</button></p>
    <p v-if="notice" class="practice-notice" role="status">{{ notice }}</p>
    <template v-if="project">
      <section class="practice-session-bar" aria-label="实践会话选择">
        <label class="field"><span>实践历史</span><select :value="session?.id ?? ''" :disabled="busy" @change="router.push({ query: { session: ($event.target as HTMLSelectElement).value } })"><option v-if="!history.length && !session" value="">暂无会话</option><option v-if="session && !history.some(item => item.id === session?.id)" :value="session.id">当前打开的会话（不在本页）</option><option v-for="item in history" :key="item.id" :value="item.id">{{ time(item.created_at) }} · {{ PRACTICE_STATUS[item.status] }} · 资料 v{{ item.context_version }}</option></select></label>
        <div class="practice-actions"><button class="secondary-command" :disabled="busy || page === 1" @click="w.historyPage(page - 1)">上一页</button><button class="secondary-command" :disabled="busy || history.length < 20" @click="w.historyPage(page + 1)">下一页</button><button class="secondary-command" :disabled="!canCreate" @click="create">创建新实践</button></div>
      </section>
      <p v-if="!context || context.is_stale" class="practice-notice">新实践需要已保存、与项目一致的资料。<RouterLink :to="`/projects/${project.id}/ai`">前往项目准备</RouterLink>。已有实践保留原快照。</p>
      <p v-if="oldContext" class="practice-notice">本次实践使用资料 v{{ session?.context_version }}，项目最新为 v{{ context?.version }}。可以继续原任务，或另建会话；原提交不会重置。</p>
      <section v-if="!session" class="practice-paper practice-empty"><h2>{{ PRACTICE_TEMPLATE.title }}</h2><code>{{ PRACTICE_TEMPLATE.signature }}</code><p>实现纯函数，逐行区分有效记录、未知分钟与已知零，返回五个统计字段。无需生成草案或拖拽节点。</p><p>先在项目准备保存资料，再创建实践。创建本身不调用模型。</p><button class="primary-command" :disabled="!canCreate" @click="create">确认固定模板，创建实践</button></section>
      <template v-else>
        <section class="practice-target" aria-label="当前目标与下一动作"><div><h2>{{ session.template.title }}</h2><p>{{ session.template.steps.find(item => item.step_key === session?.current_step_key)?.goal }}</p></div><span class="practice-status">{{ PRACTICE_STATUS[session.status] }}</span></section>
        <ol class="practice-steps" aria-label="操作步骤"><li :aria-current="session.current_step_key === 'understand' ? 'step' : undefined">理解题目</li><li :aria-current="session.current_step_key === 'implement' && session.status !== 'completed' ? 'step' : undefined">自行实现与审阅</li><li :aria-current="session.status === 'completed' ? 'step' : undefined">本次实践结束</li></ol>
        <div class="practice-layout">
          <section class="practice-task practice-paper" aria-labelledby="practice-task-title"><h2 id="practice-task-title">任务与提交物</h2><code>{{ session.template.function_signature }}</code><p>{{ session.template.task }}</p><dl><div v-for="(description, name) in session.template.output_contract" :key="name"><dt>{{ name }}</dt><dd>{{ description }}</dd></div></dl><details><summary>公开自测参考 T01 / T04</summary><p>这是声明值的核对参考，平台不会执行代码。</p><section v-for="vector in session.template.public_output_vectors" :key="vector.test_id"><h3>{{ vector.test_id }}</h3><pre tabindex="0">{{ vector.input_csv }}</pre><pre tabindex="0">{{ JSON.stringify(vector.expected, null, 2) }}</pre></section></details></section>
          <div class="practice-main">
            <section class="practice-paper practice-next" aria-labelledby="practice-next-title">
              <h2 id="practice-next-title">下一动作</h2>
              <template v-if="session.status === 'completed'"><p>本人已审阅，本次实践已结束。可以查看和复制历史提交。</p></template>
              <template v-else-if="session.status === 'cancelled'"><p>当前会话已取消。恢复会回到安全等待点，不自动重发 AI。</p></template>
              <template v-else-if="session.status === 'running'"><p>AI 请求正在运行。可以刷新已有记录或取消本次会话。</p></template>
              <template v-else-if="session.current_step_key === 'understand'"><p>{{ session.status === 'ready' ? '先阅读左侧任务。现有流程需要明确请求本步说明，然后由本人确认已阅读。' : '阅读本步说明后，可以确认并开始自行实现。' }}</p></template>
              <template v-else><p>{{ session.current_attempt ? '已有提交。可以直接审阅结束，或自行选择修改、请求建议。' : '请提交自己的函数代码。AI 建议和声明输出均为可选材料。' }}</p></template>
              <p v-if="session.status === 'failed'" class="practice-notice">AI 请求未完成，原错误已保留。可以恢复安全等待；已有代码也可以直接审阅结束。</p>
              <div class="practice-actions"><button class="secondary-command" :disabled="localBusy" @click="w.refresh">刷新当前记录</button><button v-if="actions.includes('cancel')" class="secondary-command" :disabled="localBusy" @click="act('cancel')">取消本次会话</button><button v-if="actions.includes('resume')" class="secondary-command" :disabled="localBusy" @click="act('resume')">恢复安全等待</button><button v-if="canSubmit(session) && !editing" class="primary-command" :disabled="busy" @click="edit">{{ session.current_attempt ? '修改并追加新版本' : '填写代码提交' }}</button></div>
              <p v-if="session.status === 'running'" class="muted-copy">只有操作超期后才能恢复；服务端会核对租约。</p>
            </section>
            <form v-if="editing && canSubmit(session)" class="practice-paper practice-editor" @submit.prevent="submit"><h2>提交新版本</h2><label class="field"><span>函数代码 · 最多 12000 字符</span><textarea v-model="code" class="code-textarea" maxlength="12000" spellcheck="false" required /></label><label class="field"><span>声明输出 JSON（可选，最多 8 KiB）</span><textarea v-model="output" class="code-textarea" spellcheck="false" placeholder="留空也可提交，不影响本人审阅结束" /></label><label class="field"><span>自测声明（本人提供）</span><select v-model="selfStatement"><option value="unset">不提供声明</option><option value="true">我已完成自测</option><option value="false">我尚未完成自测</option></select></label><p v-if="formError" role="alert">{{ formError }}</p><div class="practice-actions"><button class="primary-command" type="submit" :disabled="busy">{{ localBusy ? '正在保存…' : '保存为新的提交' }}</button><button class="secondary-command" type="button" :disabled="busy" @click="resetEditor">放弃本页草稿</button></div></form>
            <section v-if="session.attempts.length" class="practice-paper" aria-label="提交历史与代码"><div class="practice-section-heading"><label class="field"><span>查看提交版本</span><select v-model="selectedAttemptId" :disabled="localBusy"><option v-for="item in session.attempts" :key="item.id" :value="item.id">提交 {{ item.attempt_no }}{{ item.is_current ? ' · 当前' : ' · 历史只读' }}</option></select></label><button class="secondary-command" @click="copy">复制所选提交的代码</button></div><p v-if="copyNotice" role="status">{{ copyNotice }}</p><p v-if="!selectedCurrent" class="practice-notice">当前查看历史版本。操作和 AI 帮助只针对最新提交，请先选回当前版本。</p><pre v-if="selectedAttempt" tabindex="0" aria-label="所选提交代码">{{ selectedAttempt.code }}</pre><PracticeFeedbackPanel v-if="selectedAttempt" :key="selectedAttempt.id" :attempt="selectedAttempt" :template="session.template" :fake="fakeAdvice" /></section>
            <section v-if="actions.includes('confirm') && !editing && (session.current_step_key === 'understand' || selectedCurrent)" class="practice-paper practice-confirm"><h2>{{ session.current_step_key === 'understand' ? '确认阅读任务' : '本人审阅结束' }}</h2><label class="practice-checkbox"><input v-model="reviewed" type="checkbox" /><span>{{ session.current_step_key === 'understand' ? '我已阅读本次任务说明，准备自行实现' : '我已审阅当前提交和本页材料；如有 AI 建议，我已阅读并自行决定是否采纳' }}</span></label><button class="primary-command" :disabled="busy || !reviewed" @click="act('confirm')">{{ session.current_step_key === 'understand' ? '已阅读，开始实现' : '已审阅，结束本次实践' }}</button></section>
            <section v-if="session.status !== 'cancelled' && session.status !== 'completed'" class="practice-paper practice-help"><h2>按需 AI 帮助</h2><p>仅静态阅读当前步骤和选定提交，提出线索与建议自测。</p><div class="practice-actions"><button v-if="actions.includes('start')" class="secondary-command" :disabled="busy" @click="act('start')">请求本步 AI 说明</button><button v-if="actions.includes('review')" class="secondary-command" :disabled="busy || !selectedCurrent || editing" @click="act('review')">获取当前提交的 AI 建议</button><button v-if="actions.includes('hint')" class="secondary-command" :disabled="busy || editing || Boolean(session.current_attempt && !selectedCurrent)" @click="act('hint')">请求本步提示</button><button v-if="actions.includes('explain')" class="secondary-command" :disabled="busy || editing || Boolean(session.current_attempt && !selectedCurrent)" @click="act('explain')">讲解当前代码或步骤</button><button v-if="actions.includes('continue')" class="secondary-command" :disabled="busy" @click="act('continue')">明确重试原 AI 请求</button></div><p v-if="modelBusy" role="status">请求已发送，正在等待。刷新仅查询；取消和恢复不会自动重发。</p><span v-if="session.model_request?.provider === 'fake'" class="practice-source">Fake 工程演示，不代表真实建议质量</span><WorkflowNodeResultContent v-if="guidance" :result="guidance" /><details v-if="session.model_request"><summary>本次 AI 请求记录</summary><dl><div><dt>请求</dt><dd>#{{ session.model_request.id }} · {{ session.model_request.provider }} / {{ session.model_request.model }}</dd></div><div><dt>状态 / 错误</dt><dd>{{ session.model_request.status }} / {{ session.model_request.error_code ?? '无' }}</dd></div><div><dt>已知用量</dt><dd>{{ session.model_request.prompt_tokens ?? '未知' }} 输入 / {{ session.model_request.completion_tokens ?? '未知' }} 输出 tokens</dd></div></dl></details></section>
          </div>
        </div>
        <details class="practice-paper"><summary>版本与过程引用</summary><p>资料快照 v{{ session.context_version }} · 会话修订 {{ session.revision }} · 模板 {{ session.template_id }}/{{ session.template_version }}</p><p>会话 {{ session.id }}</p><p v-if="selectedAttempt">提交 {{ selectedAttempt.id }} · 操作 {{ selectedAttempt.operation_id ?? '未请求建议' }}</p><p>进度表示操作进度，不表示代码正确或掌握程度。</p></details>
      </template>
    </template>
  </section>
</template>
