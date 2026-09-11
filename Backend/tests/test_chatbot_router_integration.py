import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bot.router import router as bot_router


def test_chatbot_router_is_included():
    routes = [route.path for route in bot_router.routes]
    assert "/api/bot/chat" in routes
