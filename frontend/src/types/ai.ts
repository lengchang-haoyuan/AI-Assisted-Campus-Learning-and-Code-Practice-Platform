import type { ProjectDifficulty } from '@/types/project'
import type { JsonObject } from '@/types/workflow'

export type ContextSourceType = 'project' | 'user' | 'workflow_node'

export interface ContextSourceResponse {
  type: ContextSourceType
  id: number
  node_key: string | null
}

export interface ContextFieldMetadataResponse {
  version: number
  updated_at: string
  source: ContextSourceResponse
}

export interface ProjectContextValues {
  project_name: string
  language: string | null
  framework: string | null
  frontend: string | null
  backend: string | null
  database: string | null
  difficulty: ProjectDifficulty
  requirements: JsonObject[] | null
  output_requirement: string | null
  architecture: JsonObject | null
  features: string[]
  constraints: string[]
  extensions: JsonObject
}

export type ProjectContextPatch = Partial<ProjectContextValues>

export interface ProjectContextResponse {
  project_id: number
  version: number
  values: ProjectContextValues
  field_metadata: Record<string, ContextFieldMetadataResponse>
  updated_at: string
  source: ContextSourceResponse
  is_stale: boolean
  stale_fields: string[]
  stale_node_ids: number[]
}

export interface ProjectContextMutationResponse {
  context: ProjectContextResponse
  changed_fields: string[]
  stale_node_ids: number[]
}

export interface ProjectAnalysisInput {
  focus: string | null
  additional_requirements: string[]
}

export interface PromptAgentInput {
  task: string
  environment: string
  target_directory: string
  input_description: string
  output_description: string
  coding_standards: string[]
  api_requirements: string[]
  frontend_backend_relationship: string | null
}

export interface RequirementBreakdownItem {
  title: string
  description: string
  acceptance_criteria: string[]
}

export interface TechnicalChallenge {
  title: string
  reason: string
  mitigation: string
}

export interface DevelopmentStep {
  order: number
  title: string
  action: string
  verification: string
}

export interface TechnologyRecommendation {
  category: string
  choice: string
  reason: string
  alternatives: string[]
}

export interface ProjectAnalysisResult {
  result_type: 'project_analysis'
  summary: string
  requirements_breakdown: RequirementBreakdownItem[]
  technical_challenges: TechnicalChallenge[]
  development_steps: DevelopmentStep[]
  knowledge_points: string[]
  technology_recommendations: TechnologyRecommendation[]
}

export interface PromptAgentResult {
  result_type: 'prompt'
  title: string
  task: string
  language: string
  framework: string
  environment: string
  target_directory: string
  input_description: string
  output_description: string
  coding_standards: string[]
  database: string
  api_requirements: string[]
  frontend_backend_relationship: string
  generated_prompt: string
  acceptance_criteria: string[]
  risk_notes: string[]
}

export interface ReviewIssue {
  severity: 'high' | 'medium' | 'low'
  title: string
  description: string
  recommendation: string
}

export interface ReviewNextStep {
  priority: number
  action: string
  verification: string
}

export interface ProjectReviewResult {
  result_type: 'project_review'
  overall_status: 'on_track' | 'at_risk' | 'blocked' | 'completed'
  completion_summary: string
  completed_items_assessment: string[]
  issues: ReviewIssue[]
  next_steps: ReviewNextStep[]
  evidence_considered: string[]
}

export type AgentResult = ProjectAnalysisResult | PromptAgentResult | ProjectReviewResult
export type AgentType = 'project_analysis' | 'prompt' | 'project_review'
export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface AgentRecordResponse {
  request_id: number
  project_id: number | null
  agent_type: AgentType
  status: AgentStatus
  provider: string
  model: string
  context_version: number
  result: AgentResult | null
  error: { code: string; message: string } | null
  usage: {
    prompt_tokens: number | null
    completion_tokens: number | null
    latency_ms: number | null
  }
  requested_at: string
  finished_at: string | null
}
