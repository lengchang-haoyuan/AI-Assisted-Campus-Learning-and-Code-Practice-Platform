---
name: "ScholarHub · Campus Studio"
description: "薄荷画布上的校园实践工作室，以纸面、植物静物与森林墨色组织真实项目和学习任务。"
colors:
  ink: "#153c2d"
  muted: "#5c7067"
  paper: "#f9faf5"
  canvas: "#edf4ed"
  line: "#cfdfd5"
  mint: "#c9e7d8"
  mint-strong: "#155b42"
  lime-marker: "#d9ed86"
  chart-green: "#548a72"
  apricot: "#8b6838"
  white: "#ffffff"
  danger: "#b43c44"
  danger-soft: "#fff0f1"
typography:
  display:
    fontFamily: "'Studio Display', 'Studio Manrope', 'Microsoft YaHei', sans-serif"
    fontSize: "clamp(48px, 6.7vw, 100px)"
    fontWeight: 800
    lineHeight: 1.14
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "'Studio Display', 'Studio Manrope', 'Microsoft YaHei', sans-serif"
    fontSize: "clamp(34px, 4vw, 48px)"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  title:
    fontFamily: "'Studio Manrope', 'Studio Sans', 'Microsoft YaHei', 'PingFang SC', sans-serif"
    fontSize: "19px"
    fontWeight: 800
    lineHeight: 1.45
  body:
    fontFamily: "'Studio Manrope', 'Studio Sans', 'Microsoft YaHei', 'PingFang SC', sans-serif"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "'Studio Manrope', 'Studio Sans', 'Microsoft YaHei', 'PingFang SC', sans-serif"
    fontSize: "14px"
    fontWeight: 700
  metric:
    fontFamily: "'Studio Manrope', sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1
rounded:
  field: "4px"
  reference: "6px"
  icon: "8px"
  command: "9px"
  search: "10px"
  panel: "12px"
  dialog: "16px"
  pill: "999px"
spacing:
  tight: "8px"
  small: "12px"
  medium: "16px"
  dossier: "18px"
  card: "20px"
  section: "24px"
  wide: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.white}"
    rounded: "{rounded.command}"
    padding: "11px 20px"
  button-primary-hover:
    backgroundColor: "#20563f"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.command}"
    padding: "11px 20px"
  button-danger:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    rounded: "{rounded.command}"
    padding: "11px 20px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  status-chip:
    backgroundColor: "#deeee4"
    textColor: "#18533d"
    rounded: "{rounded.pill}"
    padding: "5px 12px"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
  learning-dossier:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "{spacing.dossier}"
  filter:
    backgroundColor: "{colors.mint}"
    textColor: "{colors.ink}"
    rounded: "20px"
---

# Design System: ScholarHub · Campus Studio

## Overview

**Creative North Star: "Campus Studio — 校园实践工作室"**

Campus Studio 将校园代码实践组织成一张安静、清晰的工作桌。薄荷色画布承托暖白纸面，森林墨色提供阅读与行动的重心；书本、纸张、植物和自然光让项目入口具有可辨认的材料感。布局兼顾较大的编辑式标题与紧凑的操作信息。

本记录覆盖登录后的应用壳、首页、项目库、课程与计划、学习与社区数据。图片提供氛围，项目名称、技术栈、状态、进度与统计仍由现有业务数据驱动。其他页面沿用共享样式时应保留已有任务流程、路由与权限入口。

**Key Characteristics:**

- 薄荷画布、暖白纸面、森林墨色与少量青柠标记。
- 自托管中文与拉丁字体，数字使用等宽数字排列。
- 细边框建立结构，主要卡片静止时无阴影。
- 图片项目卡、横向计划档案与克制的数据图表共享同一材料语言。

## Colors

配色以深浅绿色建立层级，青柠用于标记，暖棕用于图表中的辅助区分。具体值以前置 token 为准。

### Primary

- **森林墨色 · ink**：标题、正文、主按钮、导航选中线和主要图表序列。
- **深叶绿 · mint-strong**：项目与学习进度填充、输入框聚焦边界。

### Secondary

- **柔薄荷 · mint**：筛选选中底片和头像。
- **青柠荧光 · lime-marker**：首页标题局部标记、文本选中背景、状态环图中的完成序列。
- **叶灰绿 · chart-green**：图表中的第二序列。

### Tertiary

- **纸页暖棕 · apricot**：图表中的第三序列；保持辅助角色。

### Neutral

- **薄荷画布 · canvas**：应用壳与页面背景。
- **暖白纸面 · paper**：项目卡、计划档案、统计与报告容器。
- **灰叶文字 · muted**：说明、技术栈、日期、轴标签和未选中导航。
- **浅叶边线 · line**：页面分隔、卡片边界和导航边界。
- **纯白 · white**：主按钮文字与编辑字段内部。

危险操作沿用 danger 与 danger-soft，并保留明确的“删除”等文字。状态标签另以灰绿、浅叶绿、青柠灰绿和浅红区分未开始、进行中、完成与失败；标签文字是状态判断的依据。

**The Ink-First Rule.** 森林墨色承担主要文字与行动层级；同一页面的强调色不能削弱正文、状态和按钮的辨认。

## Typography

**Display Font:** 自托管 Noto Sans SC 标题子集，CSS 名称为 Studio Display。

**Body Font:** 自托管 Manrope 与 Noto Sans SC，CSS 名称分别为 Studio Manrope、Studio Sans；后备为 Microsoft YaHei、PingFang SC、sans-serif。

Manrope 提供拉丁字母与数字的几何节奏，Noto Sans SC 承担中文。标题采用厚重、紧密的中文轮廓；说明与操作文字保持舒展。Manrope 文件提供 400、700、800 字重；Studio Sans 的常规与加粗子集提供正文及强调文字。

### Hierarchy

- **Display**：首页问候使用前置 display token；窄屏收敛到（40px，行高 1.12）。
- **Headline**：项目库路由标题使用 headline token；学习与数据页采用相近的（32–48px）范围，760px 以下统一为（32px）。
- **Title**：项目卡标题使用 title token；计划标题为（21px），手机为（18px）；图表标题为（18px），手机为（17px）。
- **Body**：全局行高由 body token 定义。说明多为（14–16px），较长说明采用（1.6–1.75）行高；标题与技术字段允许换行。
- **Label**：主导航采用 label token；状态与辅助标签为（11–12px）。
- **Metric**：数据核心数字使用 metric token；学习概览为（34px），手机为（28px）；数据页手机数字为（26px）。专注计时器单独放大，使用等宽数字。

**The Number-Inheritance Rule.** 滚动数字的数字、符号与轨道继承所在指标的字号、字重与颜色，确保数值和百分号保持同一层级。

字体保存在 frontend/src/assets/fonts；Manrope 与 Noto Sans SC 的 SIL OFL 1.1 许可文件随资产保留。

## Layout

页面采用居中的宽画布，桌面内容容器上限为（1440px），左右各留（56px）。顶部导航将品牌、七个主要目的地、搜索和个人入口排成一行。页面标题与内容之间使用细分隔线和明确留白，组件内常用间距见前置 spacing token。

当前首页为问候与专注在左、主项目在右的编辑式组合；主项目图片占据视觉重心，最近项目与数据入口位于下方。项目库使用三列图片卡片。课程与计划使用单列横向档案：图片、标题与关联项、进度与日期、操作并排。数据页使用六列底网格，宽趋势图占四列，技术与状态图占两列；报告采用控制区与阅读区分栏。

响应式按任务顺序重排：

- **1280px 以下**：导航与品牌收紧，搜索缩窄，计划图片列收紧。
- **1040px 以下**：顶部主导航切换为底部五项导航；页面两侧留（24px），项目库为两列，统计指标为三列，图表均占半行，报告改为上下排列。
- **760px 以下**：页面两侧留（16px），首页依次为问候、主项目、专注；项目库为一列。计划图片与内容先成一行，进度和操作各占整行；统计指标为两列，图表独占一行。
- **360px 以下**：品牌与专注计时器进一步收紧。基础页面最小宽度为（320px）。

底部导航含首页、项目库、学习、数据、更多，并为安全区域留出内边距；主内容预留底部导航高度。搜索通过顶部按钮展开；“更多”打开原生模态 dialog，保留全部功能与按成员权限显示的校园入口。

## Elevation & Depth

项目卡、计划档案、指标栏、图表和报告静止时均无阴影。纸面与画布的色差、细边框、图片裁切和留白承担结构；悬停通过轻微位移或底色变化表达交互。原生导航模态窗使用深墨半透明遮罩。编辑字段聚焦时保留柔和绿环，属于操作反馈。

**The Paper-Plane Rule.** 日常内容先用纸面、边线和空间建立层级；不要给主要卡片叠加浮空阴影。

按钮颜色与位移变化采用（180ms ease）；项目进度采用（480ms cubic-bezier(.16, 1, .3, 1)），学习进度采用（550ms cubic-bezier(.22, 1, .36, 1)）。数字滚动与图表更新约（520ms）；项目卡翻面采用（620ms cubic-bezier(.2, .75, .2, 1)）。减少动态效果偏好关闭应用壳内动画与过渡。

## Shapes

圆角按功能划分：编辑字段更接近纸面切口，图标与按钮轻柔收圆，内容容器使用 panel token，模态窗使用 dialog token。状态标签与筛选外壳使用胶囊形；关联课程、项目的小标签使用 reference token。项目卡内层继承外层圆角，让封面、正面与背面保持一致边界。

图片以 object-fit: cover 裁切，避免变形。首页主图桌面宽高比为（2.1），手机为（2.5）；项目卡封面桌面高（150px），手机高（158px）。素材的植物、书页与自然光形成材料感，不额外叠加拟物边框。

## Components

### Buttons

主按钮为森林墨色实底与白字；次按钮为透明底、墨色文字和细描边；危险按钮保留红色语义；文字命令承接编辑、详情与轻量操作。常规按钮最小高度（46px），紧凑按钮为（40px）。主次按钮悬停上移（1px），主按钮加深，次按钮出现浅绿底。

键盘焦点使用（3px）绿色轮廓与（4px）外偏移。禁用、加载和确认反馈沿用已有控件行为。

### Chips and Filters

状态标签保持短词、可辨认底色和胶囊形。技术栈在项目卡中采用无底色的文字行；计划内的课程与项目引用采用浅绿小标签。分段筛选使用透明外壳、薄荷选中底片，保留既有选择状态与键盘操作。

### Cards / Containers

纸面背景、浅叶边线和 panel 圆角是主要内容容器的共同形式。项目卡先展示封面、标题与状态，再展示技术栈、说明、进度和操作。描述可收敛为两行，但完整名称仍可通过标题属性与详情查看。

“查看技术详情”翻至背面并聚焦“打开项目”；返回封面后恢复触发按钮的焦点。打开、编辑、删除沿用真实操作。隐藏面使用 inert，避免键盘进入不可见控件。

### Inputs / Fields

常规编辑字段使用白底、细描边、field 圆角与（44px）最小高度；聚焦后边框转深绿并出现柔和绿环。全局搜索使用纸面底、search 圆角与内置 SVG 搜索按钮；手机展开后占据顶部独立一行。

### Navigation

桌面主导航以文字和细下划线表示当前位置；学习子导航沿用同一规则。1040px 以上各类账号均保留退出当前登录的按钮；窄屏通过底部“更多”中的退出登录操作使用。手机底部导航采用图标加文字，选中项使用浅绿底与墨色粗字。“更多”由原生模态 dialog 承载；关闭按钮、Escape 和路由切换维持可预期的关闭行为。

### Learning Dossier and Analytics

计划档案保持单列扫描，标题、关联课程与项目、百分比、日期、编辑和删除同组出现。移动端重排这些字段，使操作位于档案末尾。统计数字保持同一墨色层级；折线、柱形与环图使用文字图例、数量及纹理辅助区分，不单靠颜色。

### Imagery and Icons

校园静物素材保存在 frontend/src/assets/campus-studio：noticeboard、books、notebook、research、components 五组封面和 brand-mark 品牌图。运行时使用 WebP，通过 srcset/sizes 在 400px 和完整尺寸之间按显示宽度与像素密度选图；PNG 与提示词作为素材来源保留。封面依项目名称与技术字段选择，学习计划复用关联项目的素材。它们是本地生成的视觉素材，不代表项目真实截图。

功能图标来自 Element Plus SVG，随目录保留 MIT 许可。界面通过 UiIcon 显示图形，交互名称由文字或 aria-label 提供；侧车预览直接内联 SVG，不依赖图标包运行时。

## Do's and Don'ts

### Do:

- **Do** 使用真实数据驱动项目标题、状态、进度、统计、空态和错误反馈。
- **Do** 复用薄荷画布、暖白纸面、森林墨色及当前字号与圆角层级。
- **Do** 保留长标题换行、清晰焦点、状态文字与减少动态效果支持。
- **Do** 在手机按任务顺序重排内容，并为固定底部导航留出空间。
- **Do** 保留字体及图标许可，使用本地校园静物素材维持材料一致性。

### Don't:

- **Don't** 将静物封面或展示样例当作真实项目成果与运营统计。
- **Don't** 给主项目卡、计划档案与图表容器增加浮空阴影。
- **Don't** 将青柠标记扩展为正文大面积底色，降低扫读层级。
- **Don't** 为改变视觉而删除原有命令、权限入口或可访问名称。

