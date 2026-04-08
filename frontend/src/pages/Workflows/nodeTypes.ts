/** Node type configuration for the visual workflow editor */

export interface NodeTypeConfig {
  type: string
  label: string
  color: string
  icon: string
  defaultDesc: string
  configFields: Array<{
    key: string
    label: string
    type: 'text' | 'textarea' | 'select' | 'slider'
    placeholder?: string
    options?: Array<{ label: string; value: string }>
    min?: number
    max?: number
    step?: number
    defaultValue?: unknown
  }>
}

export const NODE_TYPES: Record<string, NodeTypeConfig> = {
  start: {
    type: 'start',
    label: '开始',
    color: '#10b981',
    icon: '▶',
    defaultDesc: '工作流入口',
    configFields: [
      {
        key: 'input_variables',
        label: '输入变量',
        type: 'textarea',
        placeholder: '定义输入变量，如: query, context',
      },
    ],
  },
  llm_call: {
    type: 'llm_call',
    label: 'LLM 调用',
    color: '#8b5cf6',
    icon: '🧠',
    defaultDesc: '调用大语言模型',
    configFields: [
      {
        key: 'model',
        label: '模型',
        type: 'select',
        options: [
          { label: 'DeepSeek Chat', value: 'deepseek-chat' },
          { label: 'DeepSeek Reasoner', value: 'deepseek-reasoner' },
          { label: 'GPT-4o', value: 'gpt-4o' },
          { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
          { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet-20241022' },
        ],
      },
      {
        key: 'prompt',
        label: 'Prompt 模板',
        type: 'textarea',
        placeholder: '输入提示词模板，可使用 {{变量名}} 引用上游变量',
      },
      {
        key: 'temperature',
        label: '温度',
        type: 'slider',
        min: 0,
        max: 2,
        step: 0.1,
        defaultValue: 0.7,
      },
    ],
  },
  tool_call: {
    type: 'tool_call',
    label: '工具调用',
    color: '#3b82f6',
    icon: '🔧',
    defaultDesc: '调用工具/MCP',
    configFields: [
      {
        key: 'tool_name',
        label: '工具名称',
        type: 'text',
        placeholder: '输入工具名称或 MCP Server',
      },
      {
        key: 'arguments',
        label: '参数 (JSON)',
        type: 'textarea',
        placeholder: '{"key": "value"}',
      },
    ],
  },
  condition: {
    type: 'condition',
    label: '条件判断',
    color: '#f59e0b',
    icon: '⑂',
    defaultDesc: '条件分支',
    configFields: [
      {
        key: 'condition',
        label: '条件表达式',
        type: 'textarea',
        placeholder: '例如: {{result.score}} > 0.8',
      },
    ],
  },
  loop: {
    type: 'loop',
    label: '循环',
    color: '#22c55e',
    icon: '🔄',
    defaultDesc: '循环执行',
    configFields: [
      {
        key: 'max_iterations',
        label: '最大迭代次数',
        type: 'text',
        placeholder: '例如: 10',
      },
      {
        key: 'condition',
        label: '循环条件',
        type: 'textarea',
        placeholder: '例如: {{items}} is not empty',
      },
    ],
  },
  wait_input: {
    type: 'wait_input',
    label: '用户输入',
    color: '#eab308',
    icon: '✋',
    defaultDesc: '等待用户输入',
    configFields: [
      {
        key: 'prompt',
        label: '提示信息',
        type: 'textarea',
        placeholder: '向用户显示的提示消息',
      },
    ],
  },
  output: {
    type: 'output',
    label: '输出',
    color: '#6b7280',
    icon: '📤',
    defaultDesc: '输出结果',
    configFields: [
      {
        key: 'output_format',
        label: '输出格式',
        type: 'select',
        options: [
          { label: '文本', value: 'text' },
          { label: 'JSON', value: 'json' },
          { label: 'Markdown', value: 'markdown' },
        ],
      },
      {
        key: 'variable_mapping',
        label: '变量映射',
        type: 'textarea',
        placeholder: '选择要输出的变量',
      },
    ],
  },
}

/** Palette categories for the node sidebar */
export const NODE_PALETTE: Array<{ type: string; config: NodeTypeConfig }> = Object.entries(
  NODE_TYPES,
).map(([type, config]) => ({ type, config }))
