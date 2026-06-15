import { ActionIcon, Loader, Text, Title, Tooltip } from "@mantine/core";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  IconFileText,
  IconInfoCircle,
  IconSend,
  IconSparkles,
} from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";
import {
  api,
  type ChatSource,
  type StudyDocument,
} from "../../api/client";
import styles from "./ChatPanel.module.css";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
  grounded?: boolean;
}

interface Props {
  planId: number;
}

export default function ChatPanel({ planId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Cached by React Query (shared with DocumentsPanel) — used only for the hint.
  const { data: documents = [] } = useQuery<StudyDocument[]>({
    queryKey: ["documents", planId],
    queryFn: () => api.getDocuments(planId),
    enabled: !!planId,
  });
  const hasIndexedDocs = documents.some((d) => d.status === "indexed");

  const ask = useMutation({
    mutationFn: (question: string) => api.chat(planId, question),
    onSuccess: (res) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          grounded: res.grounded,
        },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          text: "Something went wrong answering that. Please try again.",
          grounded: false,
        },
      ]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, ask.isPending]);

  function send() {
    const question = input.trim();
    if (!question || ask.isPending) return;
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", text: question },
    ]);
    setInput("");
    ask.mutate(question);
  }

  return (
    <section className={styles.section}>
      <Title order={4} className={styles.title}>
        Ask your documents
      </Title>

      <div className={styles.chat}>
        <div className={styles.messages} ref={scrollRef}>
          {messages.length === 0 ? (
            <div className={styles.empty}>
              <IconSparkles size={28} stroke={1.2} color="var(--c-turquoise)" />
              <Text className={styles.emptyText}>
                {hasIndexedDocs
                  ? "Ask a question and I'll answer from your uploaded documents."
                  : "Upload a document above, then ask questions about it here."}
              </Text>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={`${styles.bubbleRow} ${
                  m.role === "user" ? styles.bubbleRowUser : ""
                }`}
              >
                <div
                  className={`${styles.bubble} ${
                    m.role === "user" ? styles.bubbleUser : styles.bubbleBot
                  }`}
                >
                  <Text className={styles.bubbleText}>{m.text}</Text>

                  {m.role === "assistant" && m.grounded === false && (
                    <div className={styles.ungrounded}>
                      <IconInfoCircle size={13} />
                      <span>Not found in your documents</span>
                    </div>
                  )}

                  {m.sources && m.sources.length > 0 && (
                    <div className={styles.sources}>
                      {m.sources.map((s, i) => (
                        <Tooltip
                          key={`${m.id}-${i}`}
                          label={s.snippet}
                          multiline
                          w={280}
                          withArrow
                          position="top"
                        >
                          <span className={styles.sourceChip}>
                            <IconFileText size={11} />
                            {s.filename} · p.{s.page + 1}
                          </span>
                        </Tooltip>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {ask.isPending && (
            <div className={styles.bubbleRow}>
              <div className={`${styles.bubble} ${styles.bubbleBot}`}>
                <Loader color="cyan" size="xs" type="dots" />
              </div>
            </div>
          )}
        </div>

        <div className={styles.inputBar}>
          <textarea
            className={styles.input}
            placeholder="Ask about your documents…"
            value={input}
            rows={1}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <ActionIcon
            variant="filled"
            color="cyan"
            size="lg"
            radius="md"
            disabled={!input.trim() || ask.isPending}
            onClick={send}
            aria-label="Send question"
          >
            <IconSend size={16} />
          </ActionIcon>
        </div>
      </div>
    </section>
  );
}
