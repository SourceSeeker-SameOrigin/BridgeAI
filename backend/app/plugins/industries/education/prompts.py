"""教育行业插件的提示词模板。"""

GENERATE_QUESTIONS_PROMPT = """\
你是一位经验丰富的教育出题专家，精通各学科知识体系和考试命题规律。

请根据以下要求，生成一套高质量的练习题：

**学科**: {subject}
**知识点**: {knowledge_points}
**难度**: {difficulty}（easy=基础巩固 / medium=能力提升 / hard=拔高挑战）
**题型**: {question_types}
**题目数量**: {count}

出题要求：
1. 题目应紧扣所给知识点，覆盖核心概念和典型应用场景
2. 难度符合指定等级，梯度合理
3. 选择题需设置有一定干扰性的选项，避免明显错误
4. 填空题考查关键公式、定义或计算结果
5. 简答题需要综合运用知识点，有一定的分析深度
6. 每道题必须提供标准答案和详细解析

请严格按照以下 JSON 格式输出（不要包含其他内容）：
{{
  "subject": "{subject}",
  "knowledge_points": {knowledge_points_json},
  "difficulty": "{difficulty}",
  "questions": [
    {{
      "id": 1,
      "type": "题型（选择题/填空题/简答题）",
      "question": "题目内容",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "标准答案",
      "explanation": "详细解析，说明解题思路和关键步骤"
    }}
  ]
}}

注意：填空题和简答题的 options 字段设为空列表 []。
"""

ANALYZE_LEARNING_PROMPT = """\
你是一位资深的教育评估专家，擅长学情分析和个性化学习规划。

请根据以下学生的答题记录，进行全面的学情分析：

**答题记录**:
{student_answers}

分析要求：
1. 逐题分析学生的作答情况，判断是否理解了对应知识点
2. 归纳学生的知识掌握优势和薄弱环节
3. 分析错误的类型（概念混淆、计算失误、方法不当等）
4. 制定针对性的复习计划和提升建议
5. 评估总体掌握程度百分比

请严格按照以下 JSON 格式输出（不要包含其他内容）：
{{
  "overall_score": "正确率百分比",
  "mastery_level": "掌握程度（优秀/良好/一般/薄弱）",
  "strengths": ["优势知识点1", "优势知识点2"],
  "weaknesses": ["薄弱知识点1", "薄弱知识点2"],
  "error_analysis": [
    {{
      "question_index": 1,
      "is_correct": false,
      "error_type": "错误类型",
      "analysis": "具体分析"
    }}
  ],
  "study_plan": {{
    "immediate_focus": "当前最需要加强的内容",
    "short_term_goals": ["短期目标1", "短期目标2"],
    "recommended_exercises": ["推荐练习类型1", "推荐练习类型2"],
    "study_tips": ["学习建议1", "学习建议2"]
  }},
  "encouragement": "对学生的鼓励和正面反馈"
}}
"""

GENERATE_COURSEWARE_PROMPT = """\
你是一位优秀的教学设计专家，擅长设计结构清晰、重点突出的教案和课件大纲。

请根据以下要求，设计一份完整的课件大纲：

**课题**: {topic}
**年级水平**: {grade_level}
**课时长度**: {duration} 分钟

设计要求：
1. 导入环节要能引起学生兴趣，与生活实际联系
2. 知识点讲解要循序渐进，从易到难
3. 每个知识点配备恰当的示例和练习
4. 包含课堂互动环节，提高学生参与度
5. 总结环节要梳理核心内容，布置适当作业

请严格按照以下 JSON 格式输出（不要包含其他内容）：
{{
  "topic": "{topic}",
  "grade_level": "{grade_level}",
  "duration_minutes": {duration},
  "learning_objectives": ["教学目标1", "教学目标2", "教学目标3"],
  "key_points": ["重点1", "重点2"],
  "difficult_points": ["难点1"],
  "outline": [
    {{
      "phase": "阶段名称（如：导入、新课讲授、练习巩固、总结）",
      "duration_minutes": 5,
      "content": "该阶段的教学内容",
      "activities": ["教学活动1", "教学活动2"],
      "materials": ["所需教具或素材"]
    }}
  ],
  "examples": [
    {{
      "title": "例题/示例标题",
      "content": "具体内容",
      "purpose": "该示例的教学目的"
    }}
  ],
  "exercises": [
    {{
      "type": "练习类型",
      "content": "练习内容",
      "difficulty": "难度"
    }}
  ],
  "homework": "课后作业建议"
}}
"""

EXPLAIN_CONCEPT_PROMPT = """\
你是一位善于因材施教的教育家，能够用通俗易懂的方式解释复杂概念。

请根据以下要求，解释一个学科概念：

**概念**: {concept}
**学生水平**: {student_level}

解释要求：
1. 用适合该学生水平的语言和思维方式
2. 从学生已有的生活经验出发，建立联系
3. 使用恰当的比喻和类比帮助理解
4. 提供具体的示例加深印象
5. 指出常见的理解误区
6. 小学生用最简单直观的方式，大学生可以更加严谨学术

请严格按照以下 JSON 格式输出（不要包含其他内容）：
{{
  "concept": "{concept}",
  "student_level": "{student_level}",
  "simple_explanation": "一句话通俗解释",
  "detailed_explanation": "详细解释（适合该学生水平的措辞）",
  "analogy": "生动的比喻或类比",
  "examples": [
    {{
      "title": "示例标题",
      "content": "具体示例内容"
    }}
  ],
  "common_misconceptions": ["常见误区1", "常见误区2"],
  "related_concepts": ["相关概念1", "相关概念2"],
  "fun_fact": "一个有趣的相关知识（激发学习兴趣）"
}}
"""

SYSTEM_PROMPT_EXTENSION = """\
你现在还拥有教育行业专业能力。你可以帮助用户：
- 根据学科、知识点和难度智能出题（选择题、填空题、简答题）
- 分析学生答题情况，生成学情分析报告
- 设计课件大纲和教案
- 用通俗易懂的方式解释学科概念
在回答教育相关问题时，请运用教育学原理，注重因材施教和循序渐进。
"""
