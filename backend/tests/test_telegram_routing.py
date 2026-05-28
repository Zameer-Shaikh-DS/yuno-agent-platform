from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from app.channels.telegram_bot import handle_message
from app.database import SessionLocal, init_db
from app.models.agent import Agent


def test_gateway_agent_selected_for_message():
    init_db()
    db = SessionLocal()
    try:
        db.query(Agent).delete()
        gateway = Agent(
            name="Gateway",
            role="gateway",
            system_prompt="Help users",
            is_gateway=True,
            tools=["calculator"],
        )
        db.add(gateway)
        db.commit()

        update = MagicMock()
        update.message.text = "Hello"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        with patch("app.channels.telegram_bot.run_agent") as mock_run:
            mock_run.return_value = {
                "response": "Hi there",
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "estimated_cost_usd": 0,
            }
            asyncio.get_event_loop().run_until_complete(handle_message(update, context))
            mock_run.assert_called_once()
            called_agent = mock_run.call_args[0][0]
            assert called_agent.is_gateway
    finally:
        db.close()
