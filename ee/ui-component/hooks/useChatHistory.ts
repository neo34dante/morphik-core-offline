import { useState, useEffect } from "react";
import { generateUUID } from "@/lib/utils";
import type { ChatMessage } from "@/components/types";

export interface ChatMeta {
  id: string;
  title: string;
  updatedAt: number;
}

const META_KEY = "morphik_chat_meta";

export default function useChatHistory() {
  const [chatList, setChatList] = useState<ChatMeta[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = localStorage.getItem(META_KEY);
    if (raw) {
      try {
        setChatList(JSON.parse(raw));
      } catch {
        setChatList([]);
      }
    }
  }, []);

  const persistList = (list: ChatMeta[]) => {
    setChatList(list);
    if (typeof window !== "undefined") {
      localStorage.setItem(META_KEY, JSON.stringify(list));
    }
  };

  const saveChatMessages = (id: string, messages: ChatMessage[]) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(`chat_${id}`, JSON.stringify(messages));
    const title = messages[0]?.content.slice(0, 20) || "New Chat";
    const meta: ChatMeta = { id, title, updatedAt: Date.now() };
    const list = [meta, ...chatList.filter(c => c.id !== id)];
    persistList(list);
  };

  const loadChatMessages = (id: string): ChatMessage[] => {
    if (typeof window === "undefined") return [];
    const raw = localStorage.getItem(`chat_${id}`);
    if (!raw) return [];
    try {
      return JSON.parse(raw);
    } catch {
      return [];
    }
  };

  const createNewChat = (): string => {
    const id = generateUUID();
    persistList([{ id, title: "New Chat", updatedAt: Date.now() }, ...chatList]);
    if (typeof window !== "undefined") {
      localStorage.setItem(`chat_${id}`, JSON.stringify([]));
    }
    return id;
  };

  const deleteChat = (id: string) => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(`chat_${id}`);
    persistList(chatList.filter(c => c.id !== id));
  };

  return { chatList, saveChatMessages, loadChatMessages, createNewChat, deleteChat };
}