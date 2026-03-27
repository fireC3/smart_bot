import asyncio
import sys

from smart_bot.state import AppState
from smart_bot.pipeline import MainChatState, MainChatPipeline
from smart_bot.frontend import CLIFrontend


async def main():
    app_state = AppState()
    frontend = CLIFrontend()
    pipeline = MainChatPipeline(frontend)

    print("Initializing SmartBot system...")
    try:
        chat_state = await MainChatState.build(app_state)
    except (ValueError, KeyError) as e:
        print(f"Configuration error: {e}")
        print("Start the web server and go to Settings to add a platform:")
        print("  SMART_BOT_PORT=8765 python -m smart_bot.web")
        sys.exit(1)

    try:
        while True:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("\nUser: ").strip()
            )
            if not raw:
                continue
            if raw.startswith("/"):
                if raw == "/bye":
                    break
                print(f"Invalid command: {raw}")
                continue
            await pipeline.run_chat_turn(chat_state, raw)
    finally:
        await chat_state.destroy()


if __name__ == "__main__":
    asyncio.run(main())
