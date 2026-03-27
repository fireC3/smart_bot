import React, { useRef, useState } from "react";
import TextareaAutosize from "react-textarea-autosize";
import styles from "./ChatInput.module.css";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  isConnected?: boolean;
}

const ChatInput: React.FC<Props> = ({ onSend, disabled = false, isConnected = true }) => {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.wrapper}>
        <div className={styles.textareaBox}>
          <TextareaAutosize
            ref={textareaRef}
            className={styles.textarea}
            placeholder={!isConnected ? "Connecting..." : disabled ? "AI is responding..." : "Type a message..."}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            minRows={1}
            maxRows={6}
            disabled={disabled}
          />
        </div>

        <div className={styles.bottom}>
          <button className={styles.attachBtn} type="button">+</button>
          <div style={{ flex: 1 }} />
          <button
            className={`${styles.sendBtn} ${!value.trim() || disabled ? styles.disabled : ""}`}
            onClick={handleSend}
            disabled={!value.trim() || disabled}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatInput;
