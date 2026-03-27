// shortcuts.ts
import { useEffect } from "react";

export const AppAction = {
  TOGGLE_CHAT_HISTORY: 'TOGGLE_CHAT_HISTORY',
} as const;

export type AppAction = typeof AppAction[keyof typeof AppAction];

/**
 * 2. 快捷键映射配置
 * 负责将物理按键组合“翻译”为业务动作
 */
function getAction(e: KeyboardEvent): AppAction | null {
  const { key } = e;

  if (key === 'Tab') return AppAction.TOGGLE_CHAT_HISTORY;

  return null;
}

/**
 * 3. 全局初始化函数
 * 负责拦截浏览器默认行为并分发自定义 Action
 * 在 main.tsx 中调用一次即可
 */
export function initShortcuts() {
  const handleKeyDown = (e: KeyboardEvent) => {
    const action = getAction(e);

    // --- 浏览器行为拦截策略 ---
    // 1. 强制拦截：无论是否匹配到 Action，都要禁止的流氓按键
    const isForbidden = 
      e.key === 'Tab' || 
      ((e.ctrlKey || e.metaKey) && ['s', 'f', 'p'].includes(e.key.toLowerCase())) ||
      (e.key === 'F5' && !import.meta.env.DEV); // 生产环境禁用刷新

    // 2. 如果匹配到了自定义 Action 或属于强制拦截范围，则切断浏览器默认行为
    if (action || isForbidden) {
      e.preventDefault();
      e.stopPropagation();
    }

    // --- 信号分发 ---
    if (action) {
      window.dispatchEvent(new CustomEvent('app-action', {
        detail: {
          action,
          target: e.target, // 保持原始触发目标，用于组件内部判断环境
          nativeEvent: e
        }
      }));
    }
  };

  window.addEventListener('keydown', handleKeyDown, { capture: true });
  
  // 顺便禁用右键菜单，增加 App 感
  window.addEventListener('contextmenu', (e) => e.preventDefault());
}

/**
 * 4. React 辅助 Hook
 * 组件通过此 Hook 订阅特定动作，并自行决定处理逻辑
 */
export function useAppAction(
  action: AppAction,
  handler: (detail: { target: EventTarget | null; nativeEvent: KeyboardEvent }) => void
) {
  useEffect(() => {
    const wrapper = (e: any) => {
      if (e.detail.action === action) {
        handler(e.detail);
      }
    };

    window.addEventListener('app-action', wrapper);
    return () => window.removeEventListener('app-action', wrapper);
  }, [action, handler]);
}