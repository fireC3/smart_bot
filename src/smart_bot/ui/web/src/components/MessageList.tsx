import { useMemo, useRef, useEffect } from "react";
import type { WSMessage } from "../hooks/useWebSocket";
import styles from "./MessageList.module.css";

interface ChatItem {
  role: "user" | "assistant" | "tool_call" | "tool_result" | "tool_group";
  id: string;
  text?: string;
  thinking?: string;
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  toolCallId?: string;
  toolResult?: string;
  isStreaming?: boolean;
  subItems?: ChatItem[];
}

interface Props {
  messages: WSMessage[];
  userMessages: { text: string; id: string }[];
}

function mergeMessages(
  wsMessages: WSMessage[],
  userMessages: { text: string; id: string }[]
): ChatItem[] {
  const items: ChatItem[] = [];
  let userIndex = 0;
  let currentAssistant: ChatItem | null = null;
  let currentThinking = "";
  const toolResults = new Map<string, string>();

  function pushUser() {
    if (userIndex < userMessages.length) {
      const um = userMessages[userIndex++];
      items.push({ role: "user", id: um.id, text: um.text });
    }
  }

  // first user message opens the conversation
  pushUser();

  for (const msg of wsMessages) {
    switch (msg.type) {
      case "thinking": {
        currentThinking += msg.text || "";
        break;
      }
      case "text": {
        if (!currentAssistant) {
          currentAssistant = {
            role: "assistant",
            id: `ai-${items.length}`,
            text: "",
            thinking: "",
            isStreaming: true,
          };
          if (currentThinking) {
            currentAssistant.thinking = currentThinking;
            currentThinking = "";
          }
          items.push(currentAssistant);
        }
        currentAssistant.text += msg.text || "";
        break;
      }
      case "tool_call":
      case "tool_confirm_request": {
        const callId = msg.call_id || "";
        const existingResult = toolResults.get(callId);
        const existingIdx = items.findIndex(
          (i) => i.role === "tool_call" && i.toolCallId === callId
        );
        const item: ChatItem = {
          role: "tool_call",
          id: `tool-${callId}`,
          toolName: msg.name,
          toolArgs: msg.arguments || (existingIdx !== -1 ? items[existingIdx].toolArgs : undefined),
          toolCallId: callId,
          toolResult: existingResult || (msg.type === "tool_confirm_request" ? "等待确认..." : "执行中..."),
        };
        if (existingIdx !== -1) {
          items[existingIdx] = item;
        } else {
          items.push(item);
        }
        break;
      }
      case "tool_result": {
        const callId = msg.call_id || "";
        const result = msg.result || "";
        toolResults.set(callId, result);
        const idx = items.findIndex(
          (i) => i.role === "tool_call" && i.toolCallId === callId
        );
        if (idx !== -1) {
          items[idx] = { ...items[idx], toolResult: result };
        } else {
          items.push({
            role: "tool_result",
            id: `toolres-${callId}`,
            toolName: msg.name,
            toolCallId: callId,
            toolResult: result,
          });
        }
        break;
      }
      case "done": {
        if (currentAssistant) {
          currentAssistant.isStreaming = false;
          currentAssistant = null;
        }
        pushUser();
        break;
      }
      case "error": {
        items.push({
          role: "assistant",
          id: `err-${items.length}`,
          text: `Error: ${msg.message}`,
        });
        currentAssistant = null;
        break;
      }
      default:
        break;
    }
  }

  if (currentAssistant) {
    currentAssistant.isStreaming = false;
  }
  // any remaining user messages
  while (userIndex < userMessages.length) {
    const um = userMessages[userIndex++];
    items.push({ role: "user", id: um.id, text: um.text });
  }

  return groupToolItems(items);
}

function groupToolItems(items: ChatItem[]): ChatItem[] {
  const grouped: ChatItem[] = [];
  let i = 0;
  while (i < items.length) {
    const item = items[i];
    if (item.role === "tool_call" || item.role === "tool_result") {
      const subItems: ChatItem[] = [item];
      let j = i + 1;
      while (j < items.length && (items[j].role === "tool_call" || items[j].role === "tool_result")) {
        subItems.push(items[j]);
        j++;
      }
      const names = [...new Set(subItems.map((s) => s.toolName).filter(Boolean))];
      grouped.push({
        role: "tool_group",
        id: `toolgrp-${grouped.length}`,
        toolName: names.join(", "),
        subItems,
      });
      i = j;
    } else {
      grouped.push(item);
      i++;
    }
  }
  return grouped;
}

export default function MessageList({ messages, userMessages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const items = useMemo(
    () => mergeMessages(messages, userMessages),
    [messages, userMessages]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items]);

  return (
    <div className={styles.list}>
      {items.map((item) => {
        if (item.role === "user") {
          return (
            <div key={item.id} className={styles.userRow}>
              <div className={styles.userBubble}>{item.text}</div>
            </div>
          );
        }

        if (item.role === "assistant") {
          return (
            <div key={item.id} className={styles.assistantRow}>
              <div className={styles.assistantBubble}>
                {item.thinking && (
                  <details className={styles.thinkingBlock}>
                    <summary>思考过程</summary>
                    <div className={styles.thinkingText}>{item.thinking}</div>
                  </details>
                )}
                <div className={styles.answerText}>
                  {item.text || (item.isStreaming ? "思考中..." : "")}
                  {item.isStreaming && (
                    <span className={styles.cursor}>|</span>
                  )}
                </div>
              </div>
            </div>
          );
        }

        if (item.role === "tool_group") {
          return (
            <div key={item.id} className={styles.toolRow}>
              <details className={styles.toolCard}>
                <summary className={styles.toolHeader}>
                  tool: {item.toolName}
                </summary>
                {item.subItems?.map((sub) => (
                  <details key={sub.id} className={styles.toolSubItem}>
                    <summary className={styles.toolSubName}>{sub.toolName}</summary>
                    {sub.toolArgs && (
                      <pre className={styles.toolArgs}>
                        {JSON.stringify(sub.toolArgs, null, 2)}
                      </pre>
                    )}
                    {sub.toolResult && (
                      <pre className={styles.toolResult}>{sub.toolResult}</pre>
                    )}
                  </details>
                ))}
              </details>
            </div>
          );
        }

        return null;
      })}
      <div ref={bottomRef} />
    </div>
  );
}
