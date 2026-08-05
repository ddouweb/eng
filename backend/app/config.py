import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ── 开发环境兜底值：仅本地起服务方便调试，生产环境绝不会用到 ────────────
# bcrypt("admin123") 的哈希
_DEV_PASSWORD_HASH = "$2b$12$3K/4jQMX94BkUoHgDM1ydevtqLdIY.jjngclPKniHi2C6aOMltWSy"
_DEV_JWT_SECRET = "dev-only-secret-do-not-use-in-production-2f8a91c7"

# ── 已知的弱口令 / 占位密钥：生产环境出现即拒绝启动 ──────────────────────
# 明文弱口令（配置里存哈希时这些不应再出现）
_WEAK_PASSWORDS = {"", "admin123", "password", "123456", "PLEASE_CHANGE_STRONG_PASSWORD"}
# 弱 / 占位 JWT 密钥（含上面的开发兜底密钥，防止误带进生产）
_WEAK_SECRETS = {
    "",
    "change-me-to-a-random-secret",
    "secret",
    "PLEASE_RUN_OPENSSL_RAND_BASE64_32",
    _DEV_JWT_SECRET,
}


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://root:root123@localhost:3306/english_coach?charset=utf8mb4"
    # 数据库连接池（按部署调优；pool_recycle 应小于 MySQL wait_timeout，默认 28800s）
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    AI_PROVIDER: str = "claude"
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501,http://localhost:5173"

    # 部署环境：dev（默认，允许兜底弱配置 + 告警）| production（拒绝弱配置启动）
    APP_ENV: str = "dev"
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = ""  # 存 bcrypt 哈希；不再默认弱口令 admin123
    JWT_SECRET_KEY: str = ""  # 必须显式配置；不再默认占位密钥
    JWT_EXPIRE_MINUTES: int = 1440

    # ── 现金激励（Cash Incentive）── 默认关，.env 显式 CASH_ENABLED=true 开启 ──
    # 周学习现金 + 里程碑奖金两层；金额累计进 member.cash_balance 虚拟钱包，线下兑现。
    # 防通胀：周现金奖「每周质量」、里程碑奖「离散成就」，不重复支付；详见 docs/Settlement.md。
    CASH_ENABLED: bool = False
    CASH_CURRENCY: str = "CNY"            # 展示符号
    CASH_WEEKLY_CAP: float = 50.0         # 周现金硬上限（元）
    # 周现金分档（星数 + 计划完成度 → 元）；档位结构见 app/cash.py _WEEKLY_TIER_SPEC
    CASH_TIER_5_FULL: float = 50.0        # 5★ 且 ≥100% 完成
    CASH_TIER_5: float = 40.0             # 5★
    CASH_TIER_4_FULL: float = 30.0        # 4★ 且 ≥100% 完成
    CASH_TIER_4: float = 20.0             # 4★
    CASH_TIER_3: float = 10.0             # 3★
    # 里程碑奖金（达标即发，幂等；每里程碑终身一次）
    CASH_MS_UNIT_BIG: float = 100.0       # 背完 ≥200 词的 Unit
    CASH_MS_UNIT_MID: float = 50.0        # 100~199 词
    CASH_MS_UNIT_SMALL: float = 30.0      # <100 词
    CASH_MS_WORDS_100: float = 10.0       # 累计掌握 100 词
    CASH_MS_WORDS_500: float = 20.0
    CASH_MS_WORDS_1000: float = 50.0
    CASH_MS_WORDS_2000: float = 100.0
    CASH_MS_STREAK_4: float = 20.0        # 连续 4 周全勤
    CASH_MS_STREAK_8: float = 50.0
    CASH_MS_STREAK_12: float = 100.0
    CASH_BADGE_REWARD: float = 10.0        # 每枚已获徽章的一次性奖励（元，跟随 CASH_ENABLED）

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("prod", "production")


settings = Settings()


def prepare_security(s: "Settings") -> None:
    """启动期安全自检：生产环境弱/空配置直接抛 RuntimeError 拒绝启动；
    开发环境兜底为可用的开发配置并打印告警。在 FastAPI lifespan 启动阶段调用。

    会就地修改传入 settings 单例的 AUTH_PASSWORD / JWT_SECRET_KEY（仅当原值为弱/空时）。
    """
    prod = s.is_production

    # ── JWT_SECRET_KEY ──
    if s.JWT_SECRET_KEY in _WEAK_SECRETS:
        if prod:
            raise RuntimeError(
                "JWT_SECRET_KEY 未配置或为已知占位值 —— 生产环境拒绝启动。"
                "请执行 `openssl rand -base64 32` 生成强随机密钥后写入 .env。"
            )
        s.JWT_SECRET_KEY = _DEV_JWT_SECRET
        logger.warning("⚠️ JWT_SECRET_KEY 未配置，已使用开发兜底密钥（请勿用于生产）。")

    # ── AUTH_PASSWORD（存 bcrypt 哈希）──
    if s.AUTH_PASSWORD in _WEAK_PASSWORDS:
        if prod:
            raise RuntimeError(
                "AUTH_PASSWORD 未配置或为弱口令 —— 生产环境拒绝启动。"
                "请在 .env 设置强密码的 bcrypt 哈希（可用 `python -c \"import bcrypt;print(bcrypt.hashpw(b'你的密码',bcrypt.gensalt()).decode())\"`）。"
            )
        s.AUTH_PASSWORD = _DEV_PASSWORD_HASH
        logger.warning("⚠️ AUTH_PASSWORD 未配置，已使用开发兜底口令 admin / admin123（请勿用于生产）。")
