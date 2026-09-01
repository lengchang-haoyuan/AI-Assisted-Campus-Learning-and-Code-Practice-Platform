# 任务完成报告：P05 Vue 前端基础框架

- 完成时间：2026-09-01 12:26:09 +08:00
- 任务范围：全栈联调，以前端实现为主
- 项目根目录：`ScholarHub/`

## 1. 修改和新增文件清单

- `frontend/src/router/index.ts`、`frontend/src/router/meta.d.ts`：P05 路由、认证元信息和守卫。
- `frontend/src/stores/auth.ts`、`frontend/src/stores/projects.ts`、`frontend/src/stores/index.ts`：认证恢复、当前用户和项目服务端状态。
- `frontend/src/api/errors.ts`、`frontend/src/api/projects.ts`：统一错误映射和 Project API 适配。
- `frontend/src/types/project.ts`、`frontend/src/domain/projects.ts`：传输类型、枚举标签和显示映射。
- `frontend/src/layouts/AppLayout.vue`：登录后顶部导航、搜索、资料入口和退出。
- `frontend/src/views/LoginView.vue`、`RegisterView.vue`：认证表单、前端即时校验和防重复提交。
- `frontend/src/views/DashboardView.vue`、`ProjectsView.vue`、`ProjectDetailView.vue`、`WorkspaceDashboardView.vue`、`ProfileView.vue`：P05 页面和真实数据状态。
- `frontend/src/components/ProjectForm.vue`、`ProjectFlipCard.vue`、`LiquidTabs.vue`、`NumberRoller.vue`：项目表单与高级交互组件。
- `frontend/src/styles/main.css`、`frontend/src/assets/`：响应式视觉系统、字体和真实图片资源。
- `PRODUCT.md`、`DESIGN.md`、`.impeccable/design.json`、`design-qa.md`：产品边界、实际设计令牌和视觉验收记录。
- `.impeccable/mocks/`、`.impeccable/review/`：确认参考图和桌面/移动端对照证据；本地构建缓存已加入忽略规则。

## 2. 本阶段关键设计和调用链

- 路由调用：`Vue Router guard → auth store → users API → Axios client → FastAPI /api/v1`。
- 项目调用：`View → project store → src/api/projects.ts → Axios client → FastAPI Project API`。
- Token 由 P03 既定 `sessionStorage` 会话存储管理；Axios 集中注入 Bearer Token，401 时清理存储和 Pinia 状态并返回登录页。
- owner 不出现在创建表单中，仍由后端根据当前 JWT 用户决定；更新和删除权限仍由后端 Service 校验。
- 列表请求使用序列号忽略陈旧响应；表单提交期间禁用命令；删除前展示不可恢复确认。
- 首页仅展示当前用户真实项目。未伪造社区动态、学习统计或 Workflow 数据。
- “轻盈实验室布告板”使用冷白、深墨、海沫绿、钴蓝和杏橙；高级交互包括液态筛选、数字滚动、卡片 3D 翻面和专注计时。

## 3. 启动命令及必要环境变量

后端：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端本地 `.env` 必须提供 `DATABASE_URL` 和至少 32 字符的 `JWT_SECRET`；真实值不得提交。

前端：

```powershell
cd frontend
pnpm dev -- --port 5173
```

前端可通过 `VITE_API_BASE_URL` 配置 API，示例为 `http://127.0.0.1:8000/api/v1`。

## 4. 执行过的测试、Lint、类型检查、构建和结果

| 检查 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 格式/差异 | `git diff --check` | 通过 | 无空白错误；Git 仅提示 Windows 换行转换。 |
| 前端 Lint | 无脚本 | 未运行 | `package.json` 未配置 lint，不新增依赖或检查策略。 |
| 前端类型 | `pnpm typecheck` | 通过 | `vue-tsc -b` 无错误；无 `any`、双重断言或关闭类型检查。 |
| 前端测试 | 无脚本 | 未运行 | 当前工程未配置组件测试框架；由真实浏览器流程补足关键行为证据。 |
| 前端构建 | `pnpm build` | 通过 | Vite 成功转换 1688 个模块。 |
| 前端依赖安全 | `pnpm audit --prod` | 通过 | 未发现已知漏洞。 |
| 后端测试 | `python -m unittest discover -s tests -v` | 通过 | 38 项测试通过。 |
| 后端编译 | `python -m compileall -q app scripts tests` | 通过 | 无语法错误。 |
| 后端依赖 | `python -m pip check` | 通过 | 无损坏依赖。 |
| 数据库连接 | `python -m scripts.check_database` | 通过 | 成功连接 `scholarhub`。 |
| 数据库结构 | `python -m scripts.verify_database_schema` | 通过 | 18 张表、33 个外键与 Models 一致。 |
| 设计检测 | `impeccable detect --json frontend/src` | 通过 | 最终问题列表为 `[]`。 |

## 5. 手工验收步骤和实际结果

1. 访问 `/register`，确认创建账号表单、即时校验和提交中状态；真实注册 API 返回成功。
2. 访问 `/login`，登录后获取 JWT，Axios 自动请求 `/users/me` 并进入 `/`。
3. 首页真实加载当前用户项目；无项目时展示空状态，有项目时展示统计和项目卡。
4. 在 `/projects` 创建项目，服务端返回 201 后进入 `/projects/:id`；刷新后数据仍来自 MySQL。
5. 在详情页编辑名称和状态，保存后页面显示服务端返回的新值。
6. 点击删除，确认框明确提示不可恢复；实际 DELETE API 返回 204，列表总数从 1 变为 0。
7. 临时停止后端，项目页显示连接失败和重试；恢复后端后重试成功清除错误。
8. 验证 `/workspace/dashboard` 和 `/profile` 正确显示真实当前用户及项目数据边界。
9. 在 1487×1058 和 390×844 检查布局，无水平溢出和文字遮挡。
10. 验证液态筛选、数字滚动、卡片翻面和专注计时；浏览器控制台最终无 warning/error。
11. 清理本轮临时项目与账号，确认残留数为 0；浏览器回到登录入口。

## 6. 未执行或失败的检查、已知问题和剩余风险

- 前端没有现成 Lint 和自动化测试脚本。本阶段未新增测试框架或依赖；剩余风险主要是未来组件变化缺少自动回归保护。
- Impeccable HERO 严格像素门为 55%，未达到 72% 阈值并保持 open。参考图包含社区动态、学习统计、多人协作和 Workflow 模板，而这些属于 P06/P07/P09；当前阶段选择真实数据边界，不用虚构模块换取像素匹配。详细证据见根目录 `design-qa.md`。
- 当前开发认证使用 `sessionStorage` Bearer Token，符合 P03 已确定设计，但不等同于生产环境的 HttpOnly Cookie 方案；P15 安全加固时应重新评估部署威胁模型。

## 7. 建议的 Git commit 信息

`feat: implement frontend foundation`

## 修改内容

- 建立完整前端路由、认证恢复、登录后布局和项目状态管理。
- 实现认证页面、Project CRUD、工作台和个人资料首条真实业务闭环。
- 建立响应式视觉系统、高级交互、设计令牌和可审查的 QA 证据。

## 文件与架构变化

- 依赖方向保持 `View/Component → Pinia Store → API Adapter → Axios Client → FastAPI`。
- 未新增依赖，未修改锁文件、公共 API、数据库结构、SQLAlchemy Models 或迁移。

## 关键设计决定

- 决定：沿用 pnpm、Vue Router、Pinia、Axios 和 Element Plus，不引入第二套状态或 UI 依赖。
- 原因：`pnpm-lock.yaml` 和现有 P00 技术栈已确定，现有依赖足以完成 P05。
- 用户确认：高级交互和“轻盈实验室布告板”基调已在前序对话确认；本阶段无新增依赖或架构变更需要额外确认。

## 兼容性与安全影响

- 公共 API：无变化。
- 数据与迁移：无变化；仅创建并清理验收数据。
- 权限、秘密和隐私：数据库凭据、JWT Secret、测试密码和 Token 均未进入源码、日志、报告或提交；`.env` 被 Git 忽略。

## 剩余风险与后续建议

- P06 实现社区 API 后，再把项目广场扩展为校园社区浏览与互动，并重新运行 HERO 像素对照。
- 增加前端测试框架属于新增依赖和检查策略，应在后续节点单独说明方案并取得确认。
