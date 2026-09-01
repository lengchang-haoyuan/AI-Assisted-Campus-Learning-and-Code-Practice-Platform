export type WorkflowStatus = 'draft' | 'ready' | 'running' | 'completed' | 'failed' | 'stale'
export type WorkflowNodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'stale'

export type JsonPrimitive = string | number | boolean | null
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[]
export interface JsonObject {
  [key: string]: JsonValue
}

export interface WorkflowProjectResponse {
  id: number
  name: string
}

export interface WorkflowResponse {
  id: number
  project: WorkflowProjectResponse
  name: string
  description: string | null
  status: WorkflowStatus
  version: number
  node_count: number
  edge_count: number
  created_at: string
  updated_at: string
}

export interface WorkflowListResponse {
  items: WorkflowResponse[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface WorkflowNodeResponse {
  id: number
  workflow_id: number
  node_key: string
  node_type: string
  name: string
  position_x: number
  position_y: number
  config: JsonObject | null
  status: WorkflowNodeStatus
  context_version: number
  created_at: string
  updated_at: string
}

export interface WorkflowEdgeResponse {
  id: number
  workflow_id: number
  source_node_id: number
  target_node_id: number
  source_node_key: string
  target_node_key: string
  condition_data: JsonObject | null
  created_at: string
}

export interface WorkflowGraphResponse {
  workflow: WorkflowResponse
  nodes: WorkflowNodeResponse[]
  edges: WorkflowEdgeResponse[]
}

export interface WorkflowListQuery {
  page: number
  pageSize: number
  projectId?: number
}

export interface WorkflowCreateInput {
  project_id: number
  name: string
  description: string | null
  status: 'draft'
}

export interface WorkflowUpdateInput {
  name?: string
  description?: string | null
  status?: WorkflowStatus
}

export interface WorkflowGraphNodeInput {
  node_key: string
  node_type: string
  name: string
  position_x: number
  position_y: number
  config: JsonObject | null
}

export interface WorkflowGraphEdgeInput {
  source_node_key: string
  target_node_key: string
  condition_data: JsonObject | null
}

export interface WorkflowGraphUpdateInput {
  version: number
  nodes: WorkflowGraphNodeInput[]
  edges: WorkflowGraphEdgeInput[]
}

export interface WorkflowNodeCreateInput extends WorkflowGraphNodeInput {}
export type WorkflowNodeUpdateInput = Partial<WorkflowGraphNodeInput>

export interface WorkflowEdgeCreateInput {
  source_node_id: number
  target_node_id: number
  condition_data: JsonObject | null
}

export type WorkflowEdgeUpdateInput = Partial<WorkflowEdgeCreateInput>
