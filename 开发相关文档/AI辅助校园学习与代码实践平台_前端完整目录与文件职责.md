# AI辅助校园学习与代码实践平台
# 前端完整目录 + 每个文件职责

> 本文档只负责前端工程。用于实际开发和毕业答辩。
> 技术路线：Vue 3 + TypeScript + Vite + Element Plus + Vue Router + Pinia + Axios + ECharts + Vue Flow。

---

## 一、前端总体职责

前端负责：

1. 页面展示
2. 用户交互
3. 路由管理
4. 前端状态管理
5. HTTP API 调用
6. Workflow 可视化
7. AI 结果展示
8. 学习数据可视化

前端**不直接访问 MySQL，也不直接调用数据库**。

总体调用：

```text
Vue 页面
  ↓
Components
  ↓
Pinia / API
  ↓
Axios
  ↓ HTTP/JSON
FastAPI
```

---

# 二、完整目录

```text
frontend/
├── public/
│   ├── favicon.ico
│   └── images/
│
├── src/
│   ├── assets/
│   │   ├── images/
│   │   ├── icons/
│   │   └── styles/
│   │       ├── index.scss
│   │       ├── reset.scss
│   │       └── variables.scss
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppNavbar.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── PageHeader.vue
│   │   │   ├── EmptyState.vue
│   │   │   ├── LoadingState.vue
│   │   │   └── ConfirmDialog.vue
│   │   │
│   │   ├── project/
│   │   │   ├── ProjectCard.vue
│   │   │   ├── ProjectForm.vue
│   │   │   ├── ProjectStatus.vue
│   │   │   └── ProjectTag.vue
│   │   │
│   │   ├── workflow/
│   │   │   ├── WorkflowCanvas.vue
│   │   │   ├── WorkflowNode.vue
│   │   │   ├── WorkflowToolbar.vue
│   │   │   ├── WorkflowSidebar.vue
│   │   │   ├── NodeConfigPanel.vue
│   │   │   ├── NodeResultPanel.vue
│   │   │   └── WorkflowRunButton.vue
│   │   │
│   │   ├── ai/
│   │   │   ├── AIChatPanel.vue
│   │   │   ├── AIResultCard.vue
│   │   │   ├── AIThinkingStatus.vue
│   │   │   └── AIPromptEditor.vue
│   │   │
│   │   └── learning/
│   │       ├── LearningPlanCard.vue
│   │       ├── TaskList.vue
│   │       ├── LearningProgress.vue
│   │       └── StudyRecordChart.vue
│   │
│   ├── views/
│   │   ├── auth/
│   │   │   ├── Login.vue
│   │   │   └── Register.vue
│   │   ├── dashboard/
│   │   │   └── Dashboard.vue
│   │   ├── project/
│   │   │   ├── ProjectList.vue
│   │   │   ├── ProjectDetail.vue
│   │   │   └── ProjectCreate.vue
│   │   ├── community/
│   │   │   ├── Community.vue
│   │   │   └── PostDetail.vue
│   │   ├── workflow/
│   │   │   └── WorkflowEditor.vue
│   │   ├── learning/
│   │   │   ├── LearningPlan.vue
│   │   │   ├── DailyTasks.vue
│   │   │   └── LearningRecords.vue
│   │   └── profile/
│   │       └── Profile.vue
│   │
│   ├── layouts/
│   │   ├── MainLayout.vue
│   │   ├── AuthLayout.vue
│   │   └── EmptyLayout.vue
│   │
│   ├── router/
│   │   └── index.ts
│   │
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── project.ts
│   │   ├── workflow.ts
│   │   ├── ai.ts
│   │   └── learning.ts
│   │
│   ├── api/
│   │   ├── request.ts
│   │   ├── auth.ts
│   │   ├── users.ts
│   │   ├── projects.ts
│   │   ├── community.ts
│   │   ├── learning.ts
│   │   ├── workflow.ts
│   │   ├── ai.ts
│   │   └── statistics.ts
│   │
│   ├── types/
│   │   ├── common.ts
│   │   ├── auth.ts
│   │   ├── user.ts
│   │   ├── project.ts
│   │   ├── community.ts
│   │   ├── learning.ts
│   │   ├── workflow.ts
│   │   ├── ai.ts
│   │   └── statistics.ts
│   │
│   ├── utils/
│   │   ├── auth.ts
│   │   ├── storage.ts
│   │   ├── format.ts
│   │   └── validate.ts
│   │
│   ├── constants/
│   │   ├── api.ts
│   │   ├── project.ts
│   │   ├── workflow.ts
│   │   └── learning.ts
│   │
│   ├── App.vue
│   └── main.ts
│
├── .env
├── .env.development
├── .env.production
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

---

# 三、入口文件

## `src/main.ts`

前端启动入口。

负责：

```text
创建 Vue 应用
↓
注册 Pinia
↓
注册 Vue Router
↓
注册 Element Plus
↓
加载全局样式
↓
mount('#app')
```

## `src/App.vue`

整个 Vue 应用根组件。

主要负责：

```vue
<RouterView />
```

不要把具体业务逻辑写在这里。

---

# 四、页面 views

## `views/auth/Login.vue`

登录页面。

负责：

- 用户名/邮箱输入
- 密码输入
- 登录按钮
- 登录失败提示
- 登录成功跳转

调用：

```text
api/auth.ts
↓
POST /api/v1/auth/login
```

## `views/auth/Register.vue`

注册页面。

负责：

- 用户名
- 邮箱
- 密码
- 确认密码
- 注册

调用：

```text
POST /api/v1/auth/register
```

## `views/dashboard/Dashboard.vue`

个人首页。

展示：

- 今日学习统计
- 学习趋势
- 项目统计
- 学习任务
- 技术栈统计
- AI 学习数据

## `views/project/ProjectList.vue`

项目列表。

负责：

- 项目展示
- 搜索
- 筛选
- 项目状态
- 项目卡片

## `views/project/ProjectCreate.vue`

创建项目。

表单：

```text
项目名称
项目描述
项目类型
难度
技术栈
标签
```

## `views/project/ProjectDetail.vue`

项目详情。

展示：

```text
项目信息
技术栈
状态
作者
标签
Workflow
社区信息
```

## `views/community/Community.vue`

校园代码社区首页。

展示：

```text
项目
帖子
热门项目
分类
搜索
```

## `views/community/PostDetail.vue`

社区内容详情：

```text
内容
作者
点赞
收藏
评论
```

## `views/workflow/WorkflowEditor.vue`

核心页面。

负责组合：

```text
WorkflowCanvas
WorkflowToolbar
WorkflowSidebar
NodeConfigPanel
NodeResultPanel
```

实现：

```text
创建节点
连接节点
配置节点
保存 Workflow
运行 Workflow
查看 AI 结果
```

## `views/learning/LearningPlan.vue`

学习计划页面。

## `views/learning/DailyTasks.vue`

每日任务页面。

## `views/learning/LearningRecords.vue`

学习记录与统计页面。

## `views/profile/Profile.vue`

个人资料和账号设置。

---

# 五、layouts

## `MainLayout.vue`

登录后的主布局：

```text
Navbar
Sidebar
Content
```

## `AuthLayout.vue`

登录/注册页面布局。

## `EmptyLayout.vue`

没有复杂导航的页面布局。

---

# 六、components/common

## `AppNavbar.vue`

顶部导航栏。

## `AppSidebar.vue`

左侧菜单。

## `PageHeader.vue`

页面标题、面包屑、操作按钮。

## `EmptyState.vue`

无数据时显示。

## `LoadingState.vue`

加载状态。

## `ConfirmDialog.vue`

删除、退出等危险操作确认。

---

# 七、components/project

## `ProjectCard.vue`

项目卡片。

输入：

```text
Project
```

输出：

```text
点击
点赞
收藏
进入详情
```

## `ProjectForm.vue`

统一处理：

```text
创建项目
编辑项目
```

## `ProjectStatus.vue`

项目状态展示。

## `ProjectTag.vue`

技术栈/项目标签展示。

---

# 八、components/workflow

这是前端核心区域。

## `WorkflowCanvas.vue`

承载 Vue Flow。

负责：

```text
Nodes
Edges
拖拽
缩放
选择
移动
```

不要在这里直接写 AI API 调用。

## `WorkflowNode.vue`

单个节点。

展示：

```text
节点名称
节点类型
运行状态
输入
输出
```

## `WorkflowToolbar.vue`

工具栏：

```text
保存
运行
撤销
重做
缩放
```

## `WorkflowSidebar.vue`

节点库。

例如：

```text
需求分析
技术栈分析
架构设计
代码生成
代码审查
学习报告
```

## `NodeConfigPanel.vue`

节点配置。

包括：

```text
Prompt
模型
参数
输入变量
输出格式
```

## `NodeResultPanel.vue`

显示 AI 节点结果。

## `WorkflowRunButton.vue`

触发 Workflow 执行。

---

# 九、components/ai

## `AIChatPanel.vue`

AI 对话区域。

## `AIResultCard.vue`

结构化 AI 结果展示。

## `AIThinkingStatus.vue`

显示：

```text
等待
执行中
成功
失败
```

## `AIPromptEditor.vue`

Prompt 编辑器。

---

# 十、components/learning

## `LearningPlanCard.vue`

学习计划卡片。

## `TaskList.vue`

任务列表。

## `LearningProgress.vue`

学习进度。

## `StudyRecordChart.vue`

学习记录图表。

---

# 十一、router/index.ts

定义路由：

```text
/login
/register

/dashboard

/projects
/projects/create
/projects/:id

/community
/community/:id

/workflow/:id

/learning
/learning/tasks
/learning/records

/profile
```

同时实现登录路由守卫：

```text
未登录
 ↓
访问受保护页面
 ↓
/login
```

---

# 十二、stores

## `auth.ts`

保存：

```text
currentUser
token
isLoggedIn
```

## `project.ts`

保存：

```text
projects
currentProject
projectContext
```

## `workflow.ts`

保存：

```text
workflow
nodes
edges
running
currentNode
```

## `ai.ts`

保存：

```text
AI 请求状态
AI 结果
当前 Agent
```

## `learning.ts`

保存：

```text
learningPlan
tasks
records
statistics
```

---

# 十三、api

## `request.ts`

Axios 核心封装。

负责：

```text
BaseURL
Token 注入
请求拦截
响应拦截
错误处理
```

## `auth.ts`

```text
register()
login()
logout()
```

## `users.ts`

```text
getMe()
updateMe()
```

## `projects.ts`

```text
getProjects()
getProject()
createProject()
updateProject()
deleteProject()
```

## `community.ts`

```text
getPosts()
getPost()
createPost()
comment()
like()
favorite()
```

## `learning.ts`

```text
getPlans()
createPlan()
getTasks()
updateTask()
createRecord()
getRecords()
```

## `workflow.ts`

```text
getWorkflow()
createWorkflow()
updateWorkflow()
runWorkflow()
getWorkflowRuns()
```

## `ai.ts`

```text
chat()
analyzeProject()
runAgent()
generateReport()
```

## `statistics.ts`

```text
getTodayStatistics()
getTrend()
getProjectStatistics()
getTechStackStatistics()
```

---

# 十四、types

TypeScript 类型只描述前端数据结构。

## `project.ts`

```text
Project
ProjectCreate
ProjectUpdate
ProjectContext
```

## `workflow.ts`

```text
Workflow
WorkflowNode
WorkflowEdge
WorkflowRun
```

## `ai.ts`

```text
AIRequest
AIResponse
AgentResult
```

---

# 十五、utils

## `auth.ts`

登录状态辅助方法。

## `storage.ts`

封装：

```text
localStorage
sessionStorage
```

## `format.ts`

日期、时间、数字格式化。

## `validate.ts`

表单校验。

---

# 十六、constants

保存固定常量：

```text
API 地址
项目状态
Workflow Node 类型
学习任务状态
```

---

# 十七、前端模块调用关系

## 登录

```text
Login.vue
 ↓
api/auth.ts
 ↓
request.ts
 ↓
FastAPI
 ↓
authStore
 ↓
Dashboard
```

## 项目

```text
ProjectCreate.vue
 ↓
ProjectForm.vue
 ↓
api/projects.ts
 ↓
FastAPI
```

## Workflow

```text
WorkflowEditor.vue
 ↓
WorkflowCanvas.vue
 ↓
workflowStore
 ↓
api/workflow.ts
 ↓
FastAPI
 ↓
Workflow Engine
 ↓
AI Agent
 ↓
AI Provider
```

## 数据统计

```text
Dashboard.vue
 ↓
statistics.ts
 ↓
FastAPI
 ↓
statistics service
 ↓
ECharts
```

---

# 十八、前端开发顺序

```text
1. Vue + Vite
2. Router
3. Pinia
4. Element Plus
5. Axios
6. 登录/注册
7. Project CRUD
8. Community
9. Learning
10. ECharts
11. Vue Flow
12. Workflow
13. AI 结果展示
14. 前后端完整联调
```

---

# 十九、答辩需要掌握

老师问“前端怎么和后端通信？”

回答：

> 前端基于 Vue 3 + TypeScript，通过 Axios 发起 HTTP/REST 请求，以 JSON 作为主要数据交换格式；FastAPI 提供后端 API，前端通过 Pinia 管理跨页面状态。

老师问“Workflow 页面怎么做？”

回答：

> 使用 Vue Flow 将后端 Workflow 的节点和边映射成可视化画布，节点配置通过组件维护，运行时调用后端 Workflow API，由后端 Agent Engine 执行。

