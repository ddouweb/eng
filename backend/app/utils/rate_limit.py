"""轻量级进程内限流（滑动窗口，按 key 聚合）。

无第三方依赖，适用于单进程部署（多进程/多实例需换 Redis 实现，见 utils.cache）。
公开未认证端点（如 /tts/generate）用它防止滥用 / DoS——避免不同文本把磁盘缓存
撑爆、或同步 I/O 钉死唯一 async worker。

设计要点：
- 滑动窗口：每个 key 维护一个时间戳 deque，剔除窗口外的旧记录后计数。
- 线程安全：一把 Lock 保护字典（FastAPI async 下竞争轻，锁粒度极小）。
- 内存有界：cleanup() 可由调用方偶发触发，清理过期/空 key。
"""
import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """窗口内未超限则记一次并返回 True；否则返回 False（调用方自行 429）。"""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max_requests:
                return False
            dq.append(now)
            return True

    def cleanup(self) -> None:
        """清掉窗口内无命中（或已过期）的 key，防长期内存增长。偶发调用即可。"""
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            stale = [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]
            for k in stale:
                del self._hits[k]
