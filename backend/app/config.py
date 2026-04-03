from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bridgeai:bridgeai_dev@localhost:5432/bridgeai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "bridgeai-dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    QWEN_API_KEY: Optional[str] = None

    # Ollama (local models)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Embedding API (optional - falls back to local TF-IDF if not set)
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: Optional[str] = None

    # MinIO / Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "bridgeai"
    MINIO_SECRET_KEY: str = "bridgeai_dev"

    # WeChat Work (企业微信)
    WECHAT_WORK_CORP_ID: str = ""
    WECHAT_WORK_AGENT_ID: str = ""
    WECHAT_WORK_SECRET: str = ""
    WECHAT_WORK_TOKEN: str = ""
    WECHAT_WORK_ENCODING_AES_KEY: str = ""

    # DingTalk (钉钉)
    DINGTALK_APP_KEY: str = ""
    DINGTALK_APP_SECRET: str = ""
    DINGTALK_ROBOT_CODE: str = ""

    # Feishu (飞书)
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_VERIFICATION_TOKEN: str = ""
    FEISHU_ENCRYPT_KEY: str = ""

    # WeChat Pay (微信支付)
    WECHAT_PAY_MCH_ID: str = ""              # 商户号
    WECHAT_PAY_API_KEY_V3: str = ""          # APIv3密钥（32字节）
    WECHAT_PAY_CERT_SERIAL_NO: str = ""      # 商户API证书序列号
    WECHAT_PAY_PRIVATE_KEY_PATH: str = ""    # 商户API私钥文件路径
    WECHAT_PAY_APP_ID: str = ""              # 应用APPID
    WECHAT_PAY_NOTIFY_URL: str = ""          # 支付结果回调URL

    # Alipay (支付宝)
    ALIPAY_APP_ID: str = ""                  # 应用APPID
    ALIPAY_PRIVATE_KEY: str = ""             # 应用私钥（PEM或裸Base64）
    ALIPAY_PUBLIC_KEY: str = ""              # 支付宝公钥（PEM或裸Base64）
    ALIPAY_NOTIFY_URL: str = ""              # 异步回调URL
    ALIPAY_RETURN_URL: str = ""              # 同步返回URL

    # App
    APP_NAME: str = "BridgeAI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
