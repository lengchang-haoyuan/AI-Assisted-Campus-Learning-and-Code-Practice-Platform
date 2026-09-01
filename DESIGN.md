---
name: ScholarHub
description: 轻盈、清晰且带有实验室布告板气质的校园学习与代码实践界面
colors:
  ink: "#17232f"
  muted-ink: "#66747d"
  paper: "#ffffff"
  canvas: "#f4f8f7"
  line: "#d9e4e1"
  seafoam: "#bfe9d8"
  seafoam-strong: "#19775f"
  cobalt: "#2867d8"
  cobalt-soft: "#e6efff"
  apricot: "#f1a468"
  danger: "#b43c44"
typography:
  display:
    fontFamily: "Reem Kufi ScholarHub, Microsoft YaHei, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "normal"
  headline:
    fontFamily: "Microsoft YaHei, PingFang SC, system-ui, sans-serif"
    fontSize: "clamp(27px, 3vw, 40px)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  body:
    fontFamily: "Microsoft YaHei, PingFang SC, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.75
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "10px 18px"
    height: "42px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
    height: "44px"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "22px"
---

# Design System: ScholarHub

## Overview

**Creative North Star: "轻盈实验室布告板"**

ScholarHub 把校园项目、学习节奏和技术状态组织成一张清爽的实验室布告板。界面以冷白纸面和深墨文字承载高密度信息，用海沫绿、钴蓝和杏橙标记不同工作区域，让社区与工作台保持轻松感，同时不退化为装饰性展示页。

视觉层级依赖明确分栏、细边框、内嵌窄色带和克制阴影。高级动效只用于表达状态变化：液态筛选负责模式切换，数字滚动负责统计变化，卡片翻面负责展示第二层技术信息；所有动效都提供减少动态效果的兼容路径。

**Key Characteristics:**

- 冷白纸面、深墨正文与三种功能强调色形成清晰对比。
- 桌面采用三栏工作面板，窄屏按任务顺序自然纵向排列。
- 圆角克制，常规容器不超过中等圆角，胶囊形仅用于状态和分段控件。
- 数据来自真实 API，空、加载、失败和重试状态与正常内容同等重要。

## Colors

调色板以清凉中性色为主体，用海沫绿表达学习进度、钴蓝表达主要操作、杏橙表达提醒与节奏变化。

### Primary

- **行动钴蓝** (`cobalt`)：主要按钮、搜索命令、焦点边框和可操作链接。
- **实验室海沫绿** (`seafoam-strong`)：进行状态、专注计时、首页左栏和选中筛选。

### Secondary

- **布告杏橙** (`apricot`)：品牌下划线、脉搏面板和轻量提醒，不与主要操作争夺注意力。

### Neutral

- **深墨** (`ink`)：标题、正文和关键数字。
- **次级墨色** (`muted-ink`)：说明、时间和弱化标签。
- **冷白纸面** (`paper`)：卡片、表单和导航表面。
- **实验台底色** (`canvas`)：应用背景。
- **轻结构线** (`line`)：边框、分隔和表单轮廓。

### Named Rules

**The Three-Marker Rule.** 海沫绿、钴蓝、杏橙各自承担一种功能语义，同一控件不得随意交换强调色。

**The Ink-First Rule.** 正文可读性先于氛围，任何浅色表面都必须使用深墨或达到等效对比度的文字。

## Typography

**Display Font:** Reem Kufi ScholarHub，回退到 Microsoft YaHei。
**Body Font:** Microsoft YaHei / PingFang SC，回退到系统无衬线字体。
**Label/Mono Font:** Reem Kufi ScholarHub 或系统等宽字体，仅用于品牌、数字和代码摘要。

**Character:** 品牌与滚动数字略带实验室器材铭牌的几何感，中文正文保持熟悉、稳定和易扫读。

### Hierarchy

- **Display**（600，24px，1）：品牌名称和数字展示。
- **Headline**（700，27–40px，1.2）：路由页主标题，不用于紧凑面板。
- **Title**（700–800，17–19px，1.3）：面板、项目卡和详情段落标题。
- **Body**（400，14px，1.75）：说明、项目描述和长文本。
- **Label**（700–800，12–14px，normal）：表单、状态和导航。

### Named Rules

**The Compact Panel Rule.** 面板内标题保持紧凑，只有路由页标题可以使用 headline 尺寸。

## Layout

桌面首页使用三栏工作面板：今日桌面、项目广场和项目脉搏。最大内容宽度随页面类型在 1180px 至 1440px 之间，页面边缘保留稳定安全区。1240px 以下重新组织脉搏区，920px 以下转为单栏，720px 以下表单、列表和项目卡全部使用单列布局。

间距以 4、8、16、24px 为基础节奏。固定格式控件使用稳定高度和网格轨道，避免加载、数字变化和长文本导致布局跳动。

## Elevation & Depth

系统采用轻量分层：静态面板由冷白表面、细边框和低对比环境阴影与背景分离；按钮和卡片仅在悬停时轻微上移。翻面项目卡使用真实 3D 透视表达信息层级，不用装饰性立体形状填充页面。

### Shadow Vocabulary

- **Ambient Panel** (`0 16px 36px rgb(23 35 47 / 9%)`)：路由级面板和工作台栏。
- **Interactive Lift** (`0 9px 20px rgb(23 35 47 / 13%)`)：可操作按钮的悬停反馈。

### Named Rules

**The Bordered-First Rule.** 先用边框和色带建立结构，阴影只提供轻微层次，不得成为主要轮廓。

## Shapes

输入、按钮和卡片使用 4–6px 克制圆角。胶囊圆角只用于状态芯片、技术标签和液态分段控件。头像保持圆形；液态筛选的选中底片使用不对称圆角变化，但控件外框尺寸保持稳定。

## Components

### Buttons

- **Shape:** 紧凑矩形，4–5px 圆角，最小高度 42px。
- **Primary:** 钴蓝底配冷白文字，标准内边距 10px 18px。
- **Hover / Focus:** 悬停上移 2px并增加环境阴影；键盘焦点使用清晰的钴蓝外环。
- **Secondary / Danger:** 次要按钮使用白底细边框；危险按钮使用浅红底和深红文字，执行前必须确认。

### Chips

- **Style:** 海沫绿浅底、深绿文字和细边框；弱化技术标签使用中性灰。
- **State:** 分段筛选的激活底片使用液态形变，未激活项保持稳定可点击区域。

### Cards / Containers

- **Corner Style:** 中等克制圆角（6px）。
- **Background:** 冷白纸面。
- **Shadow Strategy:** 仅使用 Ambient Panel 或更轻阴影。
- **Border:** 1px 轻结构线，工作区可增加不参与布局的 2px 内嵌顶部语义线。
- **Internal Padding:** 18–24px，项目卡媒体区不额外包裹卡片。

### Inputs / Fields

- **Style:** 白底、1px 中性描边、4px 圆角和至少 44px 高度。
- **Focus:** 描边切换为钴蓝并显示低透明焦点环。
- **Error / Disabled:** 错误使用浅红表面与深红文字；禁用态降低透明度但保留文字可读性。

### Navigation

顶部导航采用冷白粘性栏。当前路由通过深墨文字与海沫绿短下划线共同表达；窄屏时搜索和主导航换行，但按钮与标签不会缩成不可点击尺寸。

### Project Flip Card

项目卡正面展示真实封面、状态、技术栈和更新时间，背面展示技术详情和拥有者可执行命令。翻面保持固定卡片尺寸，使用 3D 旋转并在非活动面设置不可交互状态。

## Do's and Don'ts

### Do:

- **Do** 使用真实后端状态驱动卡片、统计、空态和错误反馈。
- **Do** 保持三种强调色的固定语义，并用文字补充颜色状态。
- **Do** 在桌面和 390px 级窄屏验证长文本、表单与危险操作。
- **Do** 为高级动效提供键盘操作、稳定尺寸和减少动态效果支持。

### Don't:

- **Don't** 用虚构的社区、Workflow 或学习统计冒充已实现业务数据。
- **Don't** 在卡片内再嵌套装饰性卡片，或用大圆角把所有区域包装成浮动容器。
- **Don't** 用单一蓝色或单一绿色覆盖所有层级和状态。
- **Don't** 让路由守卫或前端隐藏按钮代替服务端鉴权与所有权校验。
