from dataclasses import dataclass


@dataclass
class EnvironmentData:
    """环境信息"""
    os_name: str
    os_version: str
    machine_platform: str
    today: str



def get_environment_info() -> EnvironmentData:
    import platform
    import time
    return EnvironmentData(
        os_name=platform.system(),
        os_version=platform.release(),
        machine_platform=platform.machine(),
        today=time.strftime("%Y-%m-%d")
    )

def build_environment_prompt(env: EnvironmentData) -> str:
    lines = [
        "# Current Environment",
        f"- Operating System: {env.os_name} {env.os_version}",
        f"- Machine Platform: {env.machine_platform}",
        f"- Today's Date: {env.today}"
    ]
    return "\n".join(lines)
