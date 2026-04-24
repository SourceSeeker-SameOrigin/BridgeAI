from app.plugins.industries.metaphysics.prompts import SYSTEM_PROMPT

METAPHYSICS_ASSISTANT_TEMPLATE: dict = {
    "key": "metaphysics_assistant",
    "name": "玄学AI助手「道」",
    "description": "融合东方玄学智慧的专业助手，通晓八字、奇门、风水、相学、梅花、紫微、星座、天象、道医九大领域",
    "system_prompt": SYSTEM_PROMPT,
    "model_config": {
        "model_provider": "deepseek",
        "model_name": "deepseek-v4-pro",
        "temperature": 0.7,
        "max_tokens": 8192,
    },
}
