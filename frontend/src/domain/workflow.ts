import { MarkerType } from '@vue-flow/core'

import type {
  JsonObject,
  WorkflowEdgeResponse,
  WorkflowGraphEdgeInput,
  WorkflowGraphNodeInput,
  WorkflowGraphResponse,
  WorkflowGraphUpdateInput,
  WorkflowNodeResponse,
  WorkflowStatus,
} from '@/types/workflow'

export interface WorkflowNodeTemplate {
  nodeType: string
  name: string
  description: string
  tone: 'mint' | 'blue' | 'apricot' | 'ink'
  instruction: string
}

export interface WorkflowCanvasNodeData {
  databaseId: number | null
  nodeType: string
  name: string
  config: JsonObject | null
  tone: WorkflowNodeTemplate['tone']
}

export interface WorkflowCanvasEdgeData {
  databaseId: number | null
  conditionData: JsonObject | null
}

export interface WorkflowCanvasNode {
  id: string
  type: 'workflow'
  position: { x: number; y: number }
  ariaLabel: string
  data: WorkflowCanvasNodeData
}

export interface WorkflowCanvasEdge {
  id: string
  type: 'smoothstep'
  source: string
  target: string
  markerEnd: MarkerType.ArrowClosed
  data: WorkflowCanvasEdgeData
}

export const WORKFLOW_NODE_TEMPLATES: readonly WorkflowNodeTemplate[] = [
  {
    nodeType: 'requirements_analysis',
    name: '需求分析',
    description: '整理目标、约束和验收标准',
    tone: 'mint',
    instruction: '提取项目目标、核心需求、约束条件和验收标准。',
  },
  {
    nodeType: 'tech_stack_analysis',
    name: '技术栈分析',
    description: '评估前后端、数据与工程方案',
    tone: 'blue',
    instruction: '根据需求分析候选技术栈、适用范围和关键取舍。',
  },
  {
    nodeType: 'architecture_design',
    name: '架构设计',
    description: '划分模块、边界和数据流',
    tone: 'apricot',
    instruction: '输出模块职责、调用方向、数据边界和主要风险。',
  },
  {
    nodeType: 'exercise_hint',
    name: '解题提示',
    description: '从题意出发，逐步提示思路与边界',
    tone: 'mint',
    instruction: '使用中文为初学者提供渐进提示，先引导思考，不直接给出完整答案。',
  },
  {
    nodeType: 'code_explanation',
    name: '代码讲解',
    description: '解释已有代码的步骤与 Python 概念',
    tone: 'blue',
    instruction: '使用中文讲解填写的代码，说明执行顺序、返回值和容易出错的地方。',
  },
  {
    nodeType: 'answer_review',
    name: '答案评审',
    description: '静态检查答案，给出改进和测试建议',
    tone: 'apricot',
    instruction: '依据题意静态评审填写的代码，指出问题和建议测试，不声称执行或测试通过。',
  },
  {
    nodeType: 'quality_check',
    name: '质量检查',
    description: '仅可编辑，暂不支持 AI 执行',
    tone: 'ink',
    instruction: '检查结果完整性、一致性和仍需处理的问题。',
  },
] as const

export const TEACHING_NODE_TYPES = ['exercise_hint', 'code_explanation', 'answer_review'] as const
export const EXECUTABLE_NODE_TYPES = new Set(['requirements_analysis', 'tech_stack_analysis', 'architecture_design', ...TEACHING_NODE_TYPES])

export function isTeachingNode(nodeType: string): boolean {
  return TEACHING_NODE_TYPES.some(type => type === nodeType)
}

export const WORKFLOW_STATUS_LABELS: Record<WorkflowStatus, string> = {
  draft: '草稿',
  ready: '就绪',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  stale: '待更新',
}

export function getWorkflowNodeTone(nodeType: string): WorkflowNodeTemplate['tone'] {
  return WORKFLOW_NODE_TEMPLATES.find((template) => template.nodeType === nodeType)?.tone ?? 'ink'
}

export function createNodeKey(nodeType: string): string {
  const randomPart = crypto.randomUUID().replaceAll('-', '').slice(0, 12)
  return `n_${nodeType.slice(0, 20)}_${randomPart}`
}

export function createCanvasNode(
  template: WorkflowNodeTemplate,
  index: number,
): WorkflowCanvasNode {
  return {
    id: createNodeKey(template.nodeType),
    type: 'workflow',
    position: {
      x: 90 + (index % 3) * 280,
      y: 90 + Math.floor(index / 3) * 190,
    },
    ariaLabel: template.name,
    data: {
      databaseId: null,
      nodeType: template.nodeType,
      name: template.name,
      tone: template.tone,
      config: { instruction: template.instruction, expected_output: '' },
    },
  }
}

export function toCanvasNode(node: WorkflowNodeResponse): WorkflowCanvasNode {
  return {
    id: node.node_key,
    type: 'workflow',
    position: { x: node.position_x, y: node.position_y },
    ariaLabel: node.name,
    data: {
      databaseId: node.id,
      nodeType: node.node_type,
      name: node.name,
      config: node.config,
      tone: getWorkflowNodeTone(node.node_type),
    },
  }
}

export function toCanvasEdge(edge: WorkflowEdgeResponse): WorkflowCanvasEdge {
  return {
    id: `edge-${edge.id}`,
    type: 'smoothstep',
    source: edge.source_node_key,
    target: edge.target_node_key,
    markerEnd: MarkerType.ArrowClosed,
    data: {
      databaseId: edge.id,
      conditionData: edge.condition_data,
    },
  }
}

export function graphToCanvas(graph: WorkflowGraphResponse): {
  nodes: WorkflowCanvasNode[]
  edges: WorkflowCanvasEdge[]
} {
  return {
    nodes: graph.nodes.map(toCanvasNode),
    edges: graph.edges.map(toCanvasEdge),
  }
}

export function createCanvasEdge(source: string, target: string): WorkflowCanvasEdge {
  return {
    id: `edge-${source}-${target}`,
    type: 'smoothstep',
    source,
    target,
    markerEnd: MarkerType.ArrowClosed,
    data: { databaseId: null, conditionData: null },
  }
}

export function validateWorkflowGraph(
  nodes: WorkflowCanvasNode[],
  edges: WorkflowCanvasEdge[],
): string[] {
  const errors: string[] = []
  if (nodes.length > 100) errors.push('节点数量不能超过 100 个')
  if (edges.length > 300) errors.push('连线数量不能超过 300 条')

  const nodeIds = new Set(nodes.map((node) => node.id))
  const pairKeys = new Set<string>()
  const adjacency = new Map(nodes.map((node) => [node.id, [] as string[]]))
  const inDegree = new Map(nodes.map((node) => [node.id, 0]))

  for (const edge of edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      errors.push('存在引用已删除节点的连线')
      continue
    }
    if (edge.source === edge.target) errors.push('节点不能连接自身')
    const pairKey = `${edge.source}\u0000${edge.target}`
    if (pairKeys.has(pairKey)) errors.push('同一方向的节点之间只能保留一条连线')
    pairKeys.add(pairKey)
    adjacency.get(edge.source)?.push(edge.target)
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1)
  }

  const queue = [...inDegree.entries()]
    .filter(([, degree]) => degree === 0)
    .map(([nodeId]) => nodeId)
  let visited = 0
  while (queue.length > 0) {
    const nodeId = queue.pop()
    if (!nodeId) continue
    visited += 1
    for (const target of adjacency.get(nodeId) ?? []) {
      const nextDegree = (inDegree.get(target) ?? 0) - 1
      inDegree.set(target, nextDegree)
      if (nextDegree === 0) queue.push(target)
    }
  }
  if (visited !== nodes.length) errors.push('工作流不能形成循环')
  return [...new Set(errors)]
}

function toGraphNodeInput(node: WorkflowCanvasNode): WorkflowGraphNodeInput {
  return {
    node_key: node.id,
    node_type: node.data.nodeType,
    name: node.data.name,
    position_x: Math.round(node.position.x * 100) / 100,
    position_y: Math.round(node.position.y * 100) / 100,
    config: node.data.config,
  }
}

function toGraphEdgeInput(edge: WorkflowCanvasEdge): WorkflowGraphEdgeInput {
  return {
    source_node_key: edge.source,
    target_node_key: edge.target,
    condition_data: edge.data.conditionData,
  }
}

export function toGraphUpdateInput(
  version: number,
  nodes: WorkflowCanvasNode[],
  edges: WorkflowCanvasEdge[],
): WorkflowGraphUpdateInput {
  return {
    version,
    nodes: nodes.map(toGraphNodeInput),
    edges: edges.map(toGraphEdgeInput),
  }
}
