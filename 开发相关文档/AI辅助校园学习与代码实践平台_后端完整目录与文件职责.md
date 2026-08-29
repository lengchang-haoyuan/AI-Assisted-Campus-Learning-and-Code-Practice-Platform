# AI辅助校园学习与代码实践平台
# 后端完整目录 + 每个 `.py` 文件职责

> 本文档只负责后端工程。用于实际开发和毕业答辩。
> 技术路线：Python + FastAPI + Pydantic + SQLAlchemy + MySQL + Redis + JWT + AI Agent + Workflow。

---

# 一、后端总体职责

后端负责：

1. 用户认证
2. 项目管理
3. 社区业务
4. 学习计划
5. 学习记录
6. 数据统计
7. Workflow
8. AI Agent
9. ProjectContext
10. AI Provider
11. 数据持久化

核心分层：

```text
FastAPI Router
      ↓
Service
      ↓
Repository
      ↓
SQLAlchemy
      ↓
MySQL
```

AI：

```text
Service
 ↓
Workflow Engine
 ↓
Agent
 ↓
Prompt
 ↓
AIClient
 ↓
Provider
 ↓
LLM
```

---

# 二、完整目录

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis.py
│   │   └── security.py
│   │
│   ├── models/
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── course.py
│   │   ├── learning.py
│   │   ├── community.py
│   │   ├── workflow.py
│   │   ├── prompt.py
│   │   └── ai.py
│   │
│   ├── schemas/
│   │   ├── common.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── course.py
│   │   ├── learning.py
│   │   ├── community.py
│   │   ├── workflow.py
│   │   ├── prompt.py
│   │   └── ai.py
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── projects.py
│   │       ├── courses.py
│   │       ├── learning.py
│   │       ├── community.py
│   │       ├── workflows.py
│   │       ├── ai.py
│   │       └── statistics.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── course_service.py
│   │   ├── learning_service.py
│   │   ├── community_service.py
│   │   ├── workflow_service.py
│   │   ├── ai_service.py
│   │   └── statistics_service.py
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── project_repository.py
│   │   ├── course_repository.py
│   │   ├── learning_repository.py
│   │   ├── community_repository.py
│   │   └── workflow_repository.py
│   │
│   ├── ai/
│   │   ├── client.py
│   │   ├── provider.py
│   │   ├── prompts/
│   │   │   ├── project_analysis.py
│   │   │   ├── tech_stack.py
│   │   │   ├── architecture.py
│   │   │   ├── code_generation.py
│   │   │   └── review.py
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── project_analyzer.py
│   │   │   ├── tech_stack_agent.py
│   │   │   ├── architecture_agent.py
│   │   │   ├── code_agent.py
│   │   │   └── review_agent.py
│   │   ├── workflow/
│   │   │   ├── engine.py
│   │   │   ├── node.py
│   │   │   ├── edge.py
│   │   │   ├── executor.py
│   │   │   ├── state.py
│   │   │   └── registry.py
│   │   ├── context/
│   │   │   ├── project_context.py
│   │   │   ├── context_manager.py
│   │   │   └── context_schema.py
│   │   └── tools/
│   │       ├── project_tool.py
│   │       ├── database_tool.py
│   │       └── code_tool.py
│   │
│   ├── tasks/
│   │   └── workflow_tasks.py
│   │
│   └── utils/
│       ├── response.py
│       ├── logger.py
│       └── pagination.py
│
├── migrations/
├── tests/
├── schema.sql
├── requirements.txt
├── .env
└── README.md
```

---

# 三、`app/main.py`

FastAPI 启动入口。

负责：

```text
创建 FastAPI
↓
CORS
↓
注册 Router
↓
异常处理
↓
启动应用
```

核心结构：

```python
app = FastAPI()
app.include_router(api_router)
```

---

# 四、core

## `core/config.py`

统一读取环境配置：

```text
DATABASE_URL
REDIS_URL
JWT_SECRET
JWT_EXPIRE_MINUTES

OPENAI_API_KEY
DEEPSEEK_API_KEY
ANTHROPIC_API_KEY
```

真实密钥只放 `.env`。

---

## `core/database.py`

负责：

```text
SQLAlchemy Engine
Session
Base
数据库连接
```

调用：

```text
Repository
 ↓
Session
 ↓
MySQL
```

---

## `core/redis.py`

创建 Redis 客户端。

可以用于：

```text
缓存
临时任务
AI 请求缓存
热点数据
```

不需要为了“用了 Redis”而强行把所有数据放 Redis。

---

## `core/security.py`

负责：

```text
密码 Hash
密码校验
JWT 创建
JWT 解码
身份验证
```

---

# 五、models

Models 是数据库 ORM 模型。

原则：

```text
models = 数据库结构
schemas = API 数据结构
```

---

## `models/base.py`

定义 SQLAlchemy Base：

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

---

## `models/user.py`

用户模型：

```text
id
username
email
password_hash
avatar
bio
created_at
updated_at
```

关系：

```text
User
 ├── Project
 ├── LearningPlan
 ├── DailyTask
 ├── LearningRecord
 ├── LearningReport
 ├── Comment
 └── Like
```

---

## `models/project.py`

项目模型。

主要保存：

```text
项目所有者
项目名称
描述
项目类型
难度
状态
技术栈
ProjectContext
发布状态
```

Project 是社区与个人工作台之间的重要连接实体。

---

## `models/course.py`

保存：

```text
Course
CourseLesson
```

---

## `models/learning.py`

保存：

```text
LearningPlan
DailyTask
LearningRecord
LearningReport
```

---

## `models/community.py`

保存：

```text
Post
Comment
Like
Favorite
```

---

## `models/workflow.py`

保存：

```text
Workflow
WorkflowNode
WorkflowEdge
WorkflowRun
```

关系：

```text
Project
 ↓
Workflow
 ├── Nodes
 ├── Edges
 └── Runs
```

---

## `models/prompt.py`

保存：

```text
PromptTemplate
PromptVersion
```

---

## `models/ai.py`

保存 AI 调用记录：

```text
AIRequest
AIResponse
```

重点记录：

```text
Provider
Model
Input
Output
Token
Latency
Status
Error
```

---

# 六、schemas

Schema 是 API 输入输出模型。

不要直接把 SQLAlchemy Model 返回给前端。

---

## `schemas/auth.py`

定义：

```text
RegisterRequest
LoginRequest
TokenResponse
```

## `schemas/user.py`

```text
UserResponse
UserUpdate
```

## `schemas/project.py`

```text
ProjectCreate
ProjectUpdate
ProjectResponse
ProjectListResponse
```

## `schemas/course.py`

课程相关 Request / Response。

## `schemas/learning.py`

```text
LearningPlanCreate
LearningPlanResponse
TaskCreate
TaskUpdate
LearningRecordCreate
LearningReportResponse
```

## `schemas/community.py`

```text
PostCreate
PostResponse
CommentCreate
CommentResponse
```

## `schemas/workflow.py`

```text
WorkflowCreate
WorkflowUpdate
WorkflowResponse

WorkflowNodeCreate
WorkflowNodeUpdate

WorkflowEdgeCreate

WorkflowRunRequest
WorkflowRunResponse
```

## `schemas/prompt.py`

Prompt 模板输入输出。

## `schemas/ai.py`

```text
AIRequest
AIResponse
AgentRequest
AgentResult
```

---

# 七、api

API 层只负责：

```text
接收 Request
↓
Pydantic 校验
↓
身份认证
↓
调用 Service
↓
返回 Response
```

不要把复杂业务写进 Router。

---

# 八、API 文件

## `api/deps.py`

FastAPI 依赖：

```text
数据库 Session
当前用户
权限检查
```

最重要的是：

```python
get_db()
get_current_user()
```

---

## `api/v1/router.py`

统一注册：

```text
auth
users
projects
courses
learning
community
workflows
ai
statistics
```

---

## `api/v1/auth.py`

```text
POST /auth/register
POST /auth/login
POST /auth/logout
```

---

## `api/v1/users.py`

```text
GET /users/me
PUT /users/me
```

---

## `api/v1/projects.py`

```text
GET    /projects
POST   /projects
GET    /projects/{id}
PUT    /projects/{id}
DELETE /projects/{id}
```

---

## `api/v1/courses.py`

```text
GET /courses
GET /courses/{id}
```

---

## `api/v1/learning.py`

```text
GET  /learning/plans
POST /learning/plans
PUT  /learning/plans/{id}

GET  /learning/tasks
POST /learning/tasks
PUT  /learning/tasks/{id}

POST /learning/records
GET  /learning/records
```

---

## `api/v1/community.py`

```text
GET  /community/posts
POST /community/posts
GET  /community/posts/{id}

POST /community/posts/{id}/comments
POST /community/posts/{id}/like
POST /community/posts/{id}/favorite
```

---

## `api/v1/workflows.py`

```text
GET  /workflows/{id}
POST /workflows
PUT  /workflows/{id}

POST /workflows/{id}/nodes
PUT  /workflows/{id}/nodes/{node_id}

POST /workflows/{id}/run
GET  /workflows/{id}/runs
```

---

## `api/v1/ai.py`

```text
POST /ai/chat
POST /ai/analyze-project
POST /ai/run-agent
POST /ai/generate-report
```

---

## `api/v1/statistics.py`

```text
GET /statistics/today
GET /statistics/trend
GET /statistics/projects
GET /statistics/tech-stacks
```

---

# 九、services

Service 是业务逻辑层。

## `auth_service.py`

负责：

```text
注册
登录
密码验证
JWT
```

## `user_service.py`

负责用户信息。

## `project_service.py`

负责：

```text
创建项目
修改项目
删除项目
查询项目
发布项目
ProjectContext
```

## `course_service.py`

课程业务。

## `learning_service.py`

负责：

```text
学习计划
每日任务
学习记录
学习统计
学习报告
```

## `community_service.py`

负责：

```text
帖子
评论
点赞
收藏
```

## `workflow_service.py`

负责：

```text
Workflow CRUD
节点保存
边保存
运行 Workflow
```

## `ai_service.py`

负责：

```text
选择 Provider
调用 Agent
保存 AIRequest
保存 AIResponse
```

## `statistics_service.py`

负责：

```text
今日统计
趋势
项目统计
技术栈统计
```

---

# 十、repositories

Repository 专门负责数据库访问。

例如：

## `user_repository.py`

```text
get_by_id()
get_by_username()
get_by_email()
create()
update()
```

## `project_repository.py`

```text
get_by_id()
list()
create()
update()
delete()
```

## `learning_repository.py`

保存和查询：

```text
计划
任务
记录
报告
```

## `community_repository.py`

保存和查询：

```text
帖子
评论
点赞
收藏
```

## `workflow_repository.py`

保存：

```text
Workflow
Nodes
Edges
Runs
```

---

# 十一、AI 层

AI 层是系统的核心特色。

总体：

```text
AI Service
 ↓
Workflow Engine
 ↓
Agent
 ↓
AI Client
 ↓
Provider
 ↓
LLM
```

---

# 十二、`ai/provider.py`

定义统一 Provider 接口。

例如：

```python
class AIProvider:
    async def chat(self, messages, **kwargs):
        raise NotImplementedError
```

后面实现：

```text
OpenAIProvider
DeepSeekProvider
ClaudeProvider
```

这样业务代码不用绑定某一家模型。

---

# 十三、`ai/client.py`

统一 AI 调用入口：

```text
Agent
 ↓
AIClient
 ↓
Provider
 ↓
模型
```

---

# 十四、Prompt

## `prompts/project_analysis.py`

项目需求分析 Prompt。

输出：

```text
项目目标
核心功能
用户角色
需求拆解
```

## `prompts/tech_stack.py`

技术栈分析。

## `prompts/architecture.py`

系统架构分析。

## `prompts/code_generation.py`

开发 Prompt / 代码辅助。

## `prompts/review.py`

项目检查和改进建议。

---

# 十五、Agents

## `agents/base.py`

Agent 基类。

统一定义：

```text
输入 Context
执行 Prompt
调用模型
结构化输出
更新 Context
```

---

## `agents/project_analyzer.py`

负责：

```text
分析项目需求
提取功能
拆解任务
```

## `agents/tech_stack_agent.py`

负责：

```text
推荐技术栈
解释技术栈
```

## `agents/architecture_agent.py`

负责：

```text
系统模块
前后端架构
数据库设计
```

## `agents/code_agent.py`

负责：

```text
根据前置节点
生成开发 Prompt
代码建议
```

## `agents/review_agent.py`

负责：

```text
项目检查
技术栈检查
结构检查
改进建议
```

---

# 十六、AI Context

## `context/context_schema.py`

定义 ProjectContext：

```json
{
  "project_id": 1,
  "project_name": "",
  "requirements": [],
  "features": [],
  "tech_stack": [],
  "architecture": {},
  "database": {},
  "workflow_state": {},
  "learning_goal": {}
}
```

---

## `context/project_context.py`

负责读取项目上下文。

---

## `context/context_manager.py`

负责：

```text
读取 Context
更新 Context
合并节点结果
处理上下文版本
```

---

# 十七、Workflow

## `workflow/node.py`

定义：

```text
Node
NodeType
NodeStatus
```

状态：

```text
PENDING
RUNNING
SUCCESS
FAILED
STALE
```

---

## `workflow/edge.py`

定义节点依赖：

```text
source
target
condition
```

---

## `workflow/state.py`

保存：

```text
run_id
current_node
completed_nodes
failed_nodes
context
```

---

## `workflow/registry.py`

注册：

```text
project_analysis
tech_stack
architecture
code
review
```

对应不同 Agent。

---

## `workflow/executor.py`

执行一个节点：

```text
读取 Node
 ↓
读取 Context
 ↓
找到 Agent
 ↓
执行 Agent
 ↓
保存结果
 ↓
更新 Context
```

---

## `workflow/engine.py`

执行整个 Workflow：

```text
读取 Workflow
 ↓
分析节点依赖
 ↓
寻找可执行节点
 ↓
执行
 ↓
更新状态
 ↓
继续执行
```

这部分是后端 AI Workflow 的核心。

---

# 十八、AI Tools

## `tools/project_tool.py`

给 Agent 查询项目数据的工具。

## `tools/database_tool.py`

给 Agent 查询允许访问的数据。

## `tools/code_tool.py`

代码分析/处理工具。

> 工具权限必须限制，不能让模型直接拥有无限制的数据库或系统权限。

---

# 十九、tasks/workflow_tasks.py

用于异步任务。

适合：

```text
长时间 Workflow
AI 报告生成
批量分析
```

---

# 二十、utils

## `response.py`

统一 API Response。

## `logger.py`

日志。

## `pagination.py`

分页。

---

# 二十一、数据库文件

## `schema.sql`

数据库初始化 SQL。

保存：

```text
CREATE DATABASE
CREATE TABLE
PRIMARY KEY
FOREIGN KEY
INDEX
UNIQUE
JSON
```

主要表：

```text
users
projects
courses
learning_plans
daily_tasks
learning_records
learning_reports
community_posts
comments
likes
workflows
workflow_nodes
workflow_edges
workflow_runs
prompt_templates
ai_requests
```

---

# 二十二、SQLAlchemy 与 schema.sql 的关系

```text
schema.sql
    ↓
MySQL 数据库
    ↑
SQLAlchemy Models
```

两者表达的是同一套数据结构：

```text
schema.sql
= 数据库层

models/*.py
= Python ORM 层
```

---

# 二十三、后端模块调用关系

## 登录

```text
POST /auth/login
 ↓
api/v1/auth.py
 ↓
auth_service.py
 ↓
user_repository.py
 ↓
SQLAlchemy
 ↓
MySQL
 ↓
security.py
 ↓
JWT
 ↓
Response
```

---

# 二十四、项目创建

```text
POST /projects
 ↓
projects.py
 ↓
ProjectService
 ↓
ProjectRepository
 ↓
SQLAlchemy
 ↓
MySQL
```

---

# 二十五、Workflow 执行

```text
POST /workflows/{id}/run
 ↓
workflows.py
 ↓
WorkflowService
 ↓
WorkflowEngine
 ↓
WorkflowRegistry
 ↓
Agent
 ↓
ProjectContext
 ↓
Prompt
 ↓
AIClient
 ↓
AIProvider
 ↓
LLM
 ↓
Agent Result
 ↓
ContextManager
 ↓
Workflow State
 ↓
MySQL
```

---

# 二十六、AI Provider 的意义

不要：

```text
ProjectService
 ↓
OpenAI SDK
```

应该：

```text
ProjectService
 ↓
AIService
 ↓
AIClient
 ↓
AIProvider
 ├── OpenAI
 ├── DeepSeek
 └── Claude
```

这样以后换模型不会影响业务层。

---

# 二十七、ProjectContext 的意义

ProjectContext 是 AI Workflow 中共享的项目上下文。

例如：

```json
{
  "requirements": [
    "学生登录",
    "项目管理",
    "AI Workflow"
  ],
  "tech_stack": [
    "Vue 3",
    "FastAPI",
    "MySQL"
  ],
  "architecture": {
    "frontend": "Vue",
    "backend": "FastAPI"
  }
}
```

Workflow 后面的节点读取它。

例如：

```text
需求分析
 ↓
更新 Context
 ↓
技术栈分析
 ↓
更新 Context
 ↓
架构设计
 ↓
更新 Context
 ↓
代码辅助
 ↓
项目审查
```

如果技术栈发生变化：

```text
技术栈节点修改
 ↓
Context 更新
 ↓
后续架构节点重新计算
```

这就是“有上下文依赖的 Workflow”，而不是简单的几个 AI 按顺序调用。

---

# 二十八、后端数据库 ER 核心关系

```text
User
 │
 ├── Project
 │      └── Workflow
 │             ├── WorkflowNode
 │             ├── WorkflowEdge
 │             └── WorkflowRun
 │                         └── AIRequest
 │
 ├── LearningPlan
 │      └── DailyTask
 │              └── LearningRecord
 │
 └── CommunityPost
         ├── Comment
         ├── Like
         └── Favorite
```

---

# 二十九、后端开发顺序

推荐：

```text
1. FastAPI 项目初始化
2. config
3. database
4. SQLAlchemy Base
5. schema.sql
6. Models
7. Pydantic Schemas
8. JWT
9. Auth API
10. Project API
11. Community API
12. Learning API
13. Statistics API
14. Workflow API
15. AI Provider
16. AI Service
17. ProjectContext
18. Agents
19. Workflow Engine
20. AI 学习报告
```

---

# 三十、答辩技术主线

老师问：

### “你的后端是什么结构？”

回答：

> 后端采用 FastAPI 分层架构，API Router 负责请求接收和参数校验，Service 层负责业务逻辑，Repository 层负责数据库访问，SQLAlchemy 作为 ORM 与 MySQL 交互。

### “AI Agent 怎么实现？”

回答：

> 后端通过统一 AI Provider 层屏蔽不同大模型接口，Workflow Engine 根据节点依赖调度不同 Agent。Agent 读取 ProjectContext，结合对应 Prompt 调用大模型，得到结构化结果后更新 ProjectContext 和 Workflow 状态。

### “为什么需要 Workflow？”

回答：

> 因为项目开发不是一次 AI 对话，而是需求分析、技术栈、架构、代码辅助、项目审查等多个有依赖关系的步骤。Workflow 把这些步骤结构化并可视化，同时保存执行状态和上下文。

### “为什么需要 ProjectContext？”

回答：

> ProjectContext 用来保存整个项目在 AI Workflow 中的共享上下文，使后续 Agent 能理解前面节点产生的结果；当关键节点发生修改时，可以让后续依赖节点重新计算。

---

# 三十一、后端最终实现重点

最值得投入时间的是：

```text
FastAPI
SQLAlchemy
MySQL
JWT
REST API
Workflow
ProjectContext
AI Provider
AI Agent
Prompt
数据统计
```

不要在毕业设计阶段过度扩展：

```text
微服务
复杂消息队列
大型在线 IDE
完整 CI/CD
自研大模型
复杂推荐算法
大规模实时协同
```

先保证：

```text
用户
 ↓
项目
 ↓
Workflow
 ↓
Agent
 ↓
AI
 ↓
学习记录
 ↓
AI 报告
```

这一条完整闭环真正跑通。
