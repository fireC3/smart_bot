import importlib
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from smart_bot import PACKAGE_PATH
from smart_bot.config import ConfigManager
from smart_bot.frontend import WebSocketFrontend
from smart_bot.interface import PlatformConfig, ModelCapability
from smart_bot.platforms import PROVIDER_MODULE, PROVIDER_CLASS, get_provider_default_config
from smart_bot.pipeline import MainChatState, MainChatPipeline
from smart_bot.state import AppState

app = FastAPI(title="SmartBot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIST = PACKAGE_PATH / "ui" / "web" / "dist"

cfg = ConfigManager.get()


# ========== Lightweight LLM helpers (for REST endpoints) ==========


def _create_test_llm(provider: str, base_url: str, api_key: str):
    """Create a lightweight LLM for connection testing / model listing."""
    mod = importlib.import_module(PROVIDER_MODULE[provider])
    cls = getattr(mod, PROVIDER_CLASS[provider])
    platform_config = PlatformConfig(provider=provider, base_url=base_url)
    return cls(platform_config, api_key=api_key, model_name="", memory=None)


# ========== Model listing ==========


@app.get("/api/models")
async def api_models():
    settings = cfg.settings.to_dict()
    models = []

    for platform_id in sorted(cfg.platforms.items.keys()):
        platform_data = cfg.platforms.get(platform_id)
        api_key = cfg.platforms.api_key(platform_id)
        provider = platform_data.get("provider", "")

        try:
            llm = _create_test_llm(provider, platform_data.get("base_url", ""), api_key)
            await llm.enable()
            available = await llm.get_available_models()
            for mn in available:
                models.append({
                    "id": f"{platform_id}:{mn}",
                    "platform_id": platform_id,
                    "provider": provider,
                    "model": mn,
                })
            await llm.disable()
        except Exception:
            default_model = settings.get("default_model", {}).get(platform_id, "")
            if default_model:
                models.append({
                    "id": f"{platform_id}:{default_model}",
                    "platform_id": platform_id,
                    "provider": provider,
                    "model": default_model,
                })

    return models


# ========== Provider defaults ==========


@app.get("/api/providers/defaults")
async def api_provider_defaults(provider: str = ""):
    if not provider or provider not in PROVIDER_MODULE:
        return {"success": False, "error": f"Unknown provider: {provider}"}
    try:
        default_config = get_provider_default_config(provider)
        return {
            "success": True,
            "provider": default_config.provider,
            "base_url": default_config.base_url,
            "timeout": default_config.timeout,
            "max_retries": default_config.max_retries,
            "temperature": default_config.temperature,
            "max_tokens": default_config.max_tokens,
            "capability": default_config.capability.to_dict(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ========== Platform CRUD ==========


class PlatformData(BaseModel):
    provider: str
    base_url: str = ""
    timeout: int = 30
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: int | None = None
    models: list[str] = []
    capability_overrides: dict = {}
    extra_parameters: dict = {}
    api_key: str = ""


@app.get("/api/platforms")
async def api_list_platforms():
    return cfg.platforms.items


class ConnectionTestData(BaseModel):
    provider: str = ""
    base_url: str = ""
    api_key: str = ""
    platform_id: str = ""


def _resolve_test_config(data: ConnectionTestData):
    if data.platform_id and data.platform_id in cfg.platforms.items:
        pdata = cfg.platforms.get(data.platform_id)
        key = cfg.platforms.api_key(data.platform_id)
        return pdata["provider"], pdata.get("base_url", ""), key
    return data.provider, data.base_url, data.api_key


@app.post("/api/platforms/connection-test")
async def api_connection_test(data: ConnectionTestData):
    provider, base_url, api_key = _resolve_test_config(data)
    if provider not in PROVIDER_MODULE:
        return {"success": False, "error": f"Unknown provider: {provider}"}
    try:
        llm = _create_test_llm(provider, base_url, api_key)
        await llm.enable()
        await llm.disable()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/platforms/fetch-models")
async def api_fetch_models(data: ConnectionTestData):
    provider, base_url, api_key = _resolve_test_config(data)
    if provider not in PROVIDER_MODULE:
        return {"success": False, "error": f"Unknown provider: {provider}"}
    try:
        llm = _create_test_llm(provider, base_url, api_key)
        await llm.enable()
        models = await llm.get_available_models()
        await llm.disable()
        return {"success": True, "models": models}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/platforms/{platform_id}")
async def api_save_platform(platform_id: str, data: PlatformData):
    platform_dict = data.model_dump(exclude_none=True)
    provider = platform_dict.get("provider", "")
    overrides = platform_dict.pop("capability_overrides", {})
    if provider in PROVIDER_MODULE and overrides:
        try:
            defaults = get_provider_default_config(provider).capability
            capability = ModelCapability.from_defaults_and_overrides(defaults, overrides)
            platform_dict["capability"] = capability.to_dict()
        except Exception:
            pass
    await cfg.platforms.save_platform(platform_id, platform_dict)
    return {"status": "ok", "platform_id": platform_id}


@app.delete("/api/platforms/{platform_id}")
async def api_delete_platform(platform_id: str):
    await cfg.platforms.delete_platform(platform_id)
    return {"status": "ok"}


# ========== Settings ==========


class SettingsData(BaseModel):
    default_platform: str = ""
    default_model: dict = {}
    data_dir: str | None = None
    tool_inline_limit: int | None = None
    tool_preview_chars: int | None = None


@app.get("/api/settings")
async def api_get_settings():
    return cfg.settings.to_dict()


@app.put("/api/settings")
async def api_save_settings(data: SettingsData):
    await cfg.settings.update(data.model_dump(exclude_none=True))
    return {"status": "ok"}


# ========== Hooks ==========


@app.get("/api/hooks")
async def api_get_hooks():
    return cfg.hooks.data


@app.put("/api/hooks")
async def api_save_hooks(data: dict):
    await cfg.hooks.update(data)
    return {"status": "ok"}


# ========== WebSocket chat ==========


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()

    app_state = AppState()
    frontend = WebSocketFrontend(websocket)
    pipeline = MainChatPipeline(frontend)

    try:
        chat_state = await MainChatState.build(app_state)
    except Exception as e:
        await frontend.output_error(str(e))
        await frontend.on_turn_end()
        return

    # Subscribe to settings changes for live model switching
    async def on_settings_changed(data):
        new = data.get("new", {})
        new_platform = new.get("default_platform", chat_state.platform_id)
        new_model = new.get("default_model", {}).get(new_platform, chat_state.model_name)
        if (new_platform != chat_state.platform_id
                or new_model != chat_state.model_name):
            if new_platform not in cfg.platforms.items:
                return
            try:
                await chat_state.switch_llm(new_platform, new_model)
            except Exception as e:
                await frontend.output_error(f"Model switch failed: {e}")

    cfg.event_bus.subscribe("settings_changed", on_settings_changed)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            # Let the frontend handle confirmation / ask responses
            if frontend.handle_ws_message(data):
                continue

            if msg_type == "chat":
                requested = data.get("model", "")
                if requested and ":" in requested:
                    req_platform, req_model = requested.split(":", 1)
                elif requested:
                    req_platform = requested
                    req_model = cfg.settings.default_model.get(req_platform, "")
                else:
                    req_platform = chat_state.platform_id
                    req_model = chat_state.model_name

                if req_platform != chat_state.platform_id or req_model != chat_state.model_name:
                    await chat_state.switch_llm(req_platform, req_model)

                await pipeline.run_chat_turn(chat_state, data["text"])

    except WebSocketDisconnect:
        pass
    finally:
        await chat_state.destroy()


if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")


def main():
    import uvicorn
    port = int(os.environ.get("SMART_BOT_PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
