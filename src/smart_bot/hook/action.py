import asyncio
import json
import httpx
from .model import HookContent, HookEvent
import os

class BashHookAction:
    def __init__(self, cmd: str):
        self.cmd = cmd
        self._process: asyncio.subprocess.Process | None = None

    async def run(self, event: HookEvent, arguments: dict, hook_content: HookContent) -> tuple[bool, str]:
        try:
            self._process = await asyncio.create_subprocess_shell(
                cmd=self.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=hook_content.cwd,
                env= {
                    **os.environ,
                    "HOOK_EVENT": event.value,
                    "HOOK_ARGUMENTS": json.dumps(arguments)
                }
            )
            stdout, stderr = await self._process.communicate()
            result_text = stdout.decode().strip()
            error_text = stderr.decode().strip()
            if self._process.returncode == 0:
                return True, result_text
            else:
                return False, f"Error (code {self._process.returncode}): {error_text}"
        except Exception as e:
            return False, f"Execution failed: {str(e)}"
        finally:
            self._process = None

    async def stop(self) -> tuple[bool, str]:
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
                await self._process.wait()
                return True, "Process terminated"
            except Exception as e:
                return False, f"Stop failed: {str(e)}"
        return True, "No process running"

    def to_str(self) -> str:
        return f"{self.cmd}"

    def to_dict(self) -> dict:
        return {"type": self.__class__.__name__, "cmd": self.cmd}

    @staticmethod
    def from_dict(data: dict) -> "BashHookAction":
        return BashHookAction(cmd=data["cmd"])


class HttpHookAction:
    def __init__(self, url: str, headers: dict = None, payload: dict = None):
        self.url = url
        self.headers = headers or {}
        self.payload = payload or {}
        self._client: httpx.AsyncClient | None = None

    async def run(self, event: HookEvent, arguments: dict, hook_content: HookContent) -> tuple[bool, str]:
        async with httpx.AsyncClient(headers=self.headers, timeout=None) as client:
            self._client = client
            try:
                response = await client.post(self.url, json={**self.payload, **arguments, "event": event.value})
                if response.is_success:
                    return True, response.text
                else:
                    return False, f"HTTP Error {response.status_code}: {response.text}"
            except httpx.RequestError as exc:
                return False, f"Network error occurred: {str(exc)}"
            finally:
                self._client = None

    async def stop(self) -> tuple[bool, str]:
        if self._client:
            await self._client.aclose()
            return True, "HTTP request cancelled"
        return True, "No active request to stop"

    def to_str(self) -> str:
        return f"POST {self.url}"

    def to_dict(self) -> dict:
        return {"type": self.__class__.__name__, "url": self.url, "headers": self.headers, "payload": self.payload}

    @staticmethod
    def from_dict(data: dict) -> "HttpHookAction":
        return HttpHookAction(url=data["url"], headers=data.get("headers"), payload=data.get("payload"))
