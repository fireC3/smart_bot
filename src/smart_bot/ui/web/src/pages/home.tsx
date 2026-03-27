import { useState, useCallback, useMemo, useRef } from "react";
import ChatInput from "../components/ChatInput";
import Live2DCanvas from "../components/Live2DView";
import MessageList from "../components/MessageList";
import useWebSocket from "../hooks/useWebSocket";
import type { WSMessage } from "../hooks/useWebSocket";
import styles from "./home.module.css";

interface HomeProps {
  onOpenSettings?: () => void;
}

export default function Home({ onOpenSettings }: HomeProps) {
  const { messages, sendMessage, sendToolConfirm, isConnected } = useWebSocket();
  const [userMessages, setUserMessages] = useState<{ text: string; id: string }[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const counterRef = useRef(0);

  const handleSend = useCallback(
    (text: string) => {
      const id = `user-${++counterRef.current}`;
      setUserMessages((prev) => [...prev, { text, id }]);
      sendMessage(text);
    },
    [sendMessage]
  );

  const isStreaming = useMemo(() => {
    if (messages.length === 0) return false;
    const last = messages[messages.length - 1];
    return last.type !== "done" && last.type !== "error";
  }, [messages]);

  const [handledIds, setHandledIds] = useState(new Set<string>());

  const pendingConfirms = useMemo(() => {
    const doneIds = new Set(
      messages
        .filter((m) => m.type === "tool_result")
        .map((m) => m.call_id!)
        .filter(Boolean)
    );
    return messages.filter(
      (m) => m.type === "tool_confirm_request"
        && m.call_id
        && !doneIds.has(m.call_id)
        && !handledIds.has(m.call_id)
    ) as (WSMessage & { type: "tool_confirm_request" })[];
  }, [messages, handledIds]);

  const handleConfirm = useCallback(
    (callId: string, confirmed: boolean) => {
      setHandledIds((prev) => new Set(prev).add(callId));
      sendToolConfirm(callId, confirmed);
    },
    [sendToolConfirm]
  );

  return (
    <div className={styles.home}>
      <div className={styles.stage}>
        <button className={styles.settingsBtn} onClick={onOpenSettings} title="Settings">
          +
        </button>

        <div className={`${styles.mainArea} ${sidebarOpen ? styles.mainAreaShifted : ""}`}>
          <div className={styles.live2d}>
            <Live2DCanvas modelUrl="/HoshinoAi/Hoshino_Ai.model3.json" />
          </div>

          <div className={styles.input}>
            <ChatInput onSend={handleSend} disabled={isStreaming} isConnected={isConnected} />
          </div>

          {!sidebarOpen && (
            <button
              className={styles.floatingToggle}
              onClick={() => setSidebarOpen(true)}
            >
              ◀ 对话
            </button>
          )}
        </div>

        <div className={`${styles.sidebar} ${!sidebarOpen ? styles.collapsed : ""}`}>
          <div className={styles.sidebarHeader}>
            <span className={styles.sidebarTitle}>对话历史</span>
            <button
              className={styles.toggleBtn}
              onClick={() => setSidebarOpen(false)}
            >
              ▶
            </button>
          </div>
          <div className={styles.sidebarMessages}>
            <MessageList messages={messages} userMessages={userMessages} />
          </div>
        </div>

        {pendingConfirms.map((pc) => (
          <div key={pc.call_id} className={styles.modalOverlay}>
            <div className={styles.modal}>
              <div className={styles.modalTitle}>
                是否执行工具？
              </div>
              <div className={styles.modalToolName}>{pc.name}</div>
              <pre className={styles.modalArgs}>
                {pc.arguments
                  ? JSON.stringify(pc.arguments, null, 2)
                  : "(无参数)"}
              </pre>
              <div className={styles.modalButtons}>
                <button
                  className={styles.denyBtn}
                  onClick={() => handleConfirm(pc.call_id!, false)}
                >
                  拒绝
                </button>
                <button
                  className={styles.confirmBtn}
                  onClick={() => handleConfirm(pc.call_id!, true)}
                >
                  允许
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
