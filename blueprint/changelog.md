# BridgeAI Blueprint 变更记录

## [v0.3.0] - 2026-04-01

### 新增前端详细设计

**前端设计方案 (03-frontend-design.md) 新增：**
- 设计原则：深色主题 + 毛玻璃风格 + 克制动效
- 技术栈：React 18 + TypeScript + Ant Design 5 + Tailwind CSS 4 + Zustand
- 主题配色方案：深蓝黑底 + 靛蓝紫品牌色
- 整体布局：侧边栏(可收起) + 顶栏 + 主内容区
- 7 个核心页面详细线框图：
  - 登录页（粒子背景 + 毛玻璃卡片）
  - 对话页（三栏：会话列表 + 消息区 + 上下文面板）
  - Agent 管理（卡片网格 + 编辑抽屉）
  - MCP 连接器（连接状态 + 市场）
  - 知识库（文档列表 + 检索测试）
  - 仪表盘（统计卡片 + 图表）
  - 系统设置（Tab 式分区）
- 前端目录结构（pages/components/stores/hooks/api）
- 关键交互：SSE 流式对话、工具调用可视化、消息气泡样式
- 响应式断点（Desktop/Tablet/Mobile）

### 上下文分析改为大模型一次性输出

**核心变更**：删除规则引擎（情绪检测、意图分类、复杂度评估），改为在 Prompt 中注入分析指令，大模型回答时同时输出 `<analysis>` JSON 分析块。

**产品方案 (00-product-overview.md) 更新：**
- 架构图：上下文引擎从 4 个子模块简化为"大模型一次性输出"
- 管线从 7 阶段简化为 6 阶段（合并上下文分析到 Prompt 融合 + 响应解析）
- 核心能力表：意图识别和情绪检测标注为"大模型输出，无规则引擎"
- 新增 1.2.1 节：大模型上下文分析指令设计（`<analysis>` 标签方案）
- 模型路由简化：首次用默认模型，后续基于上一轮分析结果动态调整

**技术架构 (01-tech-architecture.md) 更新：**
- 管线流程图重绘为 6 阶段版本
- 目录结构 `engine/` 简化：
  - 删除 `emotion_detector.py`, `intent_classifier.py`, `complexity_assessor.py`, `context_analyzer.py`
  - 新增 `context_parser.py`（解析 `<analysis>` JSON）
  - `prompt_optimizer.py` 更新为含分析指令注入
- 新增 3.0.3.1 节：ContextParser 响应解析器实现

**迭代计划 (02-iteration-plan.md) 更新：**
- Sprint 1.2 任务更新：新增 Prompt 融合 + 分析指令、熔断降级
- Phase 1 交付物新增：大模型一次性输出分析、智能模型路由 + 熔断降级
- Phase 2 新增：Few-shot 学习循环任务

---

## [v0.2.0] - 2026-04-01

### 融合 Fortune AI Agent 设计

参考项目：`/Users/waishixiaoxiaoya/IdeaProjects/宜信/fortune-ai-agent`（Spring Boot + Spring AI 企业级金融 AI 顾问系统）

**产品方案 (00-product-overview.md) 更新：**
- 产品架构图重构：新增上下文引擎层、模型适配层，标注 4 维多租户隔离
- Agent 引擎核心能力扩充：新增 7 阶段管线、Prompt 四层融合、智能模型路由(5层)、熔断降级、3级记忆、子任务委派、Few-shot 学习循环
- 新增 7 阶段对话处理管线详细说明（含每阶段输入输出）
- Agent 类型：新增层级 Agent 支持（主 Agent → 子 Agent 委派）
- 模型适配层：新增智能路由配置 + 熔断降级链配置
- 数据库设计大幅增强：
  - agents 表增加 parent_agent_id, task_key, knowledge_base_id, model_config
  - messages 表增加快速字段（intent, emotion, task_key, model_used, 性能指标）
  - 新增 message_intents 表（意图识别详情，懒加载）
  - 新增 message_emotions 表（情绪检测详情，懒加载）
  - 新增 message_ratings 表（用户评分，Few-shot 数据源）
  - 新增 agent_memories 表（3级记忆，含向量索引）

**技术架构 (01-tech-architecture.md) 更新：**
- 对话流程重构为 7 阶段管线完整流程图
- 新增核心设计章节（第三节），含 6 个关键模块的 Python 实现示意：
  - 智能模型路由器（5层决策树）
  - 熔断降级链（CircuitBreaker）
  - Prompt 四层融合器（PromptOptimizer）
  - 3 级记忆管理（MemoryManager）
  - 4 维多租户隔离（TenantMiddleware + SQLAlchemy 事件）
  - Redis 缓存策略（key 设计 + TTL 策略）
- 目录结构新增模块：
  - `engine/`: 上下文引擎（情绪检测、意图分类、复杂度评估、Prompt 优化、反馈学习）
  - `providers/`: LLM 提供商适配层（注册中心 + 多提供商适配器）
  - `agents/model_router.py`: 智能模型路由
  - `agents/circuit_breaker.py`: 熔断降级
  - `middleware/content_filter.py`: 敏感词过滤

---

## [v0.1.0] - 2026-04-01

### 初始方案
- 产品总览方案 (`00-product-overview.md`)
- 技术架构详细设计 (`01-tech-architecture.md`)
- 迭代计划 (`02-iteration-plan.md`)
