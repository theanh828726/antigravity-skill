from __future__ import annotations

import asyncio
import logging

from .bot.app import VtfBot
from .config import get_settings
from .core.llm import AnthropicLLM
from .core.orchestrator import Orchestrator
from .db.session import Database
from .integrations.google import build_integrations


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    if not s.telegram_bot_token or not s.owner_ids:
        raise SystemExit("Thiếu TELEGRAM_BOT_TOKEN hoặc OWNER_TELEGRAM_IDS trong .env")
    s.data_dir.mkdir(parents=True, exist_ok=True)
    integ = build_integrations(s)
    logging.getLogger(__name__).info("Tích hợp Google: %s", integ.mode)
    bot = VtfBot(s, Database(s.database_url), integ, Orchestrator(AnthropicLLM(s), s.max_agent_iterations))
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
