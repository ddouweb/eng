"""
批量预生成单词发音到 static/audio/（暖缓存）。

懒生成已能在首次播放时自动落盘；本脚本用于一次性预热全部单词，
让首次练习即可秒回音频、并完全离线可用。

用法:
    cd backend
    python scripts/pregenerate_tts.py            # 预生成所有英文单词（默认 en）
    python scripts/pregenerate_tts.py --lang zh  # 生成中文释义读音（按需）

幂等：已缓存的词会直接读文件跳过，可重复运行。
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 让脚本能 import app 包（支持 `python scripts/xxx.py` 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Windows 控制台中文输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from sqlalchemy import select  # noqa: E402

from app.ai.tts_service import get_tts_service  # noqa: E402
from app.database import async_session_factory, engine  # noqa: E402
from app.models.word import Word  # noqa: E402


async def run(lang: str) -> None:
    svc = get_tts_service()

    async with async_session_factory() as session:
        rows = (await session.execute(select(Word.english))).scalars().all()
    # 不同 Unit 可能有重复词，去重
    unique = sorted({w.strip() for w in rows if w and w.strip()})
    print(f"共 {len(unique)} 个唯一英文词条，开始预生成 (lang={lang}) ...")

    done = failed = 0
    for i, w in enumerate(unique, 1):
        try:
            audio = await svc.generate(w, lang)
            if audio:
                done += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {w}: {e}")
        if i % 50 == 0:
            print(f"  进度 {i}/{len(unique)}（成功 {done}，失败 {failed}）")

    print(f"\n完成: 成功 {done}, 失败 {failed}")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量预生成单词 TTS 暖缓存")
    parser.add_argument("--lang", default="en", help="语言 (en/zh)，默认 en")
    args = parser.parse_args()
    asyncio.run(run(args.lang))


if __name__ == "__main__":
    main()
