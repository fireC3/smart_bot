# test_hook.py
import pytest
from smart_bot.hook import Hook, HookEvent, HookManager, HookContent, BashHookAction, HttpHookAction
from pathlib import Path
import asyncio
import json

@pytest.mark.asyncio
async def test_bash_action():
    """测试 BashHookAction"""
    print("\n" + "="*50)
    print("测试 BashHookAction")
    print("="*50)
    
    # 创建 HookContent
    hook_content = HookContent(cwd=Path("."))
    
    # 测试1: 成功的命令
    print("\n[测试1] 执行成功的命令: echo 'Hello World'")
    bash_action = BashHookAction(cmd='echo "Hello World"')
    success, result = await bash_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    print(f"结果: {result}")
    
    # 测试2: 执行 ls 命令
    print("\n[测试2] 执行: ls -la")
    bash_action = BashHookAction(cmd='ls -la')
    success, result = await bash_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    print(f"结果:\n{result}")
    
    # 测试3: 失败的命令
    print("\n[测试3] 执行失败的命令: nonexistent_command")
    bash_action = BashHookAction(cmd='nonexistent_command')
    success, result = await bash_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    print(f"结果: {result}")
    
    # 测试4: 长时间运行的命令（会被 timeout 限制）
    print("\n[测试4] 长时间运行的命令: sleep 3")
    bash_action = BashHookAction(cmd='sleep 3')
    try:
        async with asyncio.timeout(2):
            success, result = await bash_action.run(HookEvent.SESSION_START, {}, hook_content)
        print(f"成功: {success}")
        print(f"结果: {result}")
    except asyncio.TimeoutError:
        print("⏰ 命令超时（符合预期）")
        await bash_action.stop()
    
    # 测试5: 多行输出
    print("\n[测试5] 多行输出: echo 'line1\\nline2\\nline3'")
    bash_action = BashHookAction(cmd='echo -e "line1\nline2\nline3"')
    success, result = await bash_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    print(f"结果:\n{result}")

@pytest.mark.asyncio
async def test_http_action():
    """测试 HttpHookAction"""
    print("\n" + "="*50)
    print("测试 HttpHookAction")
    print("="*50)
    
    # 注意：这里需要有一个 HTTP 服务器在运行
    # 如果没有服务器，测试会失败
    
    # 测试1: 使用公共测试 API
    print("\n[测试1] 使用公共测试 API: https://httpbin.org/post")
    http_action = HttpHookAction(
        url="https://httpbin.org/post",
        headers={"Content-Type": "application/json"},
        payload={"test": "data", "message": "Hello from hook"}
    )
    hook_content = HookContent(cwd=Path("."))
    success, result = await http_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    if success:
        try:
            data = json.loads(result)
            print(f"响应: {json.dumps(data, indent=2)[:500]}")
        except:
            print(f"结果: {result[:200]}")
    
    # 测试2: 使用 JSONPlaceholder API
    print("\n[测试2] 使用 JSONPlaceholder API")
    http_action = HttpHookAction(
        url="https://jsonplaceholder.typicode.com/posts",
        headers={"Content-Type": "application/json"},
        payload={"title": "test", "body": "content", "userId": 1}
    )
    success, result = await http_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    if success:
        print(f"响应: {result[:200]}")
    
    # 测试3: GET 请求（通过自定义 payload）
    print("\n[测试3] GET 请求到 https://httpbin.org/get")
    http_action = HttpHookAction(
        url="https://httpbin.org/get",
        payload={"param1": "value1", "param2": "value2"}
    )
    success, result = await http_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    if success:
        print(f"响应: {result[:200]}")
    
    # 测试4: 错误的 URL
    print("\n[测试4] 错误的 URL")
    http_action = HttpHookAction(
        url="https://this-domain-does-not-exist-12345.com/api",
        payload={"test": "data"}
    )
    success, result = await http_action.run(HookEvent.SESSION_START, {}, hook_content)
    print(f"成功: {success}")
    print(f"错误: {result}")

@pytest.mark.asyncio
async def test_bash_hook_in_manager():
    """测试在 HookManager 中使用 Bash Hook"""
    print("\n" + "="*50)
    print("测试 Bash Hook 在 HookManager 中")
    print("="*50)
    
    manager = HookManager(HookContent(cwd=Path(".")))
    
    # 注册多个 Bash hooks
    hook1 = Hook(
        hook=BashHookAction(cmd='echo "Hook 1 executed"'),
        timeout=3,
        block_on_failure=False
    )
    
    hook2 = Hook(
        hook=BashHookAction(cmd='echo "Hook 2 executed"'),
        timeout=3,
        block_on_failure=True
    )
    
    manager.register_hook(HookEvent.SESSION_START, hook1)
    manager.register_hook(HookEvent.SESSION_START, hook2)
    
    print("\n执行 SESSION_START hooks...")
    blocked, results = await manager.run_hooks(
        HookEvent.SESSION_START,
        {"session_id": "test_session", "user": "admin"}
    )
    
    print(f"\n阻断状态: {blocked}")
    for i, result in enumerate(results):
        print(f"Hook {i+1}: 成功={result.is_success}, 阻断={result.blocked}")
        print(f"  结果: {result.result}")

@pytest.mark.asyncio
async def test_http_hook_in_manager():
    """测试在 HookManager 中使用 HTTP Hook"""
    print("\n" + "="*50)
    print("测试 HTTP Hook 在 HookManager 中")
    print("="*50)
    
    manager = HookManager(HookContent(cwd=Path(".")))
    
    # 注册 HTTP hook
    http_hook = Hook(
        hook=HttpHookAction(
            url="https://httpbin.org/post",
            headers={"X-Test": "hook-test"},
            payload={"event": "session_start", "timestamp": "2024-01-01"}
        ),
        timeout=5,
        block_on_failure=False,
        match_tool=["bash", "python"]  # 只匹配特定工具
    )
    
    manager.register_hook(HookEvent.TOOL_CALL_BEFORE, http_hook)
    
    # 测试匹配的工具
    print("\n[测试1] 匹配的工具 (bash)")
    blocked, results = await manager.run_hooks(
        HookEvent.TOOL_CALL_BEFORE,
        {"tool_name": "bash", "tool_arguments": {"command": "ls"}}
    )
    print(f"阻断状态: {blocked}")
    for result in results:
        print(f"成功: {result.is_success}, 结果: {result.result[:100]}")
    
    # 测试不匹配的工具
    print("\n[测试2] 不匹配的工具 (unknown_tool)")
    blocked, results = await manager.run_hooks(
        HookEvent.TOOL_CALL_BEFORE,
        {"tool_name": "unknown_tool", "tool_arguments": {}}
    )
    print(f"阻断状态: {blocked}")
    print(f"Hooks 执行数量: {len(results)} (应该为0，因为不匹配)")

@pytest.mark.asyncio
async def test_stop_mechanism():
    """测试停止机制"""
    print("\n" + "="*50)
    print("测试停止机制")
    print("="*50)

    # 测试 Bash Action 停止
    print("\n[测试 Bash Stop]")
    bash_action = BashHookAction(cmd='sleep 10')
    task = asyncio.create_task(bash_action.run(HookEvent.SESSION_START, {}, HookContent(cwd=Path("."))))

    await asyncio.sleep(0.5)  # 让进程启动
    success, message = await bash_action.stop()
    print(f"停止结果: {success}, 消息: {message}")

    try:
        await task
    except Exception as e:
        print(f"任务被取消: {e}")

    # 测试 HTTP Action 停止
    print("\n[测试 HTTP Stop]")
    http_action = HttpHookAction(
        url="https://httpbin.org/delay/10",  # 延迟10秒的响应
        payload={"test": "data"}
    )
    task = asyncio.create_task(http_action.run(HookEvent.SESSION_START, {}, HookContent(cwd=Path("."))))

    await asyncio.sleep(0.5)
    success, message = await http_action.stop()
    print(f"停止结果: {success}, 消息: {message}")

    try:
        await task
    except Exception as e:
        print(f"HTTP任务结束: {e}")

    await asyncio.sleep(0.1)

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "🔧"*25)
    print("开始测试 Hook Actions")
    print("🔧"*25)
    
    try:
        # 测试 Bash Action
        await test_bash_action()
        
        # 测试 HTTP Action（需要网络连接）
        print("\n" + "🌐"*25)
        print("HTTP 测试需要网络连接")
        print("🌐"*25)
        await test_http_action()
        
        # 测试在 Manager 中使用
        await test_bash_hook_in_manager()
        await test_http_hook_in_manager()
        
        # 测试停止机制
        await test_stop_mechanism()
        
        print("\n" + "✅"*25)
        print("所有测试完成")
        print("✅"*25)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 运行所有测试
    asyncio.run(run_all_tests())