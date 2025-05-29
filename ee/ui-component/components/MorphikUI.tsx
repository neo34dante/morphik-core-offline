"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/ui/sidebar";
import DocumentsSection from "@/components/documents/DocumentsSection";
import SearchSection from "@/components/search/SearchSection";
import ChatSection from "@/components/chat/ChatSection";
import AgentChatSection from "@/components/chat/AgentChatSection";
import GraphSection from "@/components/GraphSection";
import { ConnectorList } from "@/components/connectors/ConnectorList";
import { AlertSystem } from "@/components/ui/alert-system";
import { extractTokenFromUri, getApiBaseUrlFromUri } from "@/lib/utils";
import { MorphikUIProps } from "./types";
import { cn } from "@/lib/utils";
import { setupLogging } from "@/lib/log";
import { generateUUID } from "@/lib/utils";
import useChatHistory from "@/hooks/useChatHistory";

// Default API base URL
const DEFAULT_API_BASE_URL = "http://localhost:8000";

// Disable excessive logging unless debug is enabled
setupLogging();

const MorphikUI: React.FC<MorphikUIProps> = ({
  connectionUri,
  apiBaseUrl = DEFAULT_API_BASE_URL,
  isReadOnlyUri = false, // Default to editable URI
  onUriChange,
  onBackClick,
  initialFolder = null,
  initialSection = "documents",
  onDocumentUpload,
  onDocumentDelete,
  onDocumentClick,
  onFolderCreate,
  onFolderClick,
  onSearchSubmit,
  onChatSubmit,
  onAgentSubmit,
  onGraphClick,
  onGraphCreate,
  onGraphUpdate,
}) => {
  // State to manage connectionUri internally if needed
  const [currentUri, setCurrentUri] = useState(connectionUri);

  // Update internal state when prop changes
  useEffect(() => {
    setCurrentUri(connectionUri);
  }, [connectionUri]);

  // Valid section types, now matching the updated MorphikUIProps
  type SectionType = "documents" | "search" | "chat" | "graphs" | "agent" | "connections";

  useEffect(() => {
    // Ensure initialSection from props is a valid SectionType before setting
    setActiveSection(initialSection as SectionType);
  }, [initialSection]);

  // Handle URI changes from sidebar
  const handleUriChange = (newUri: string) => {
    console.log("MorphikUI: URI changed to:", newUri);
    setCurrentUri(newUri);
    onUriChange?.(newUri);
  };

  const [activeSection, setActiveSection] = useState<SectionType>(initialSection as SectionType);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const { chatList, loadChatMessages, createNewChat } = useChatHistory();
  const [currentChatId, setCurrentChatId] = useState<string>("");

  useEffect(() => {
    if (chatList.length === 0) {
      const id = createNewChat();
      setCurrentChatId(id);
    } else if (!currentChatId) {
      setCurrentChatId(chatList[0].id);
    }
  }, [chatList]);

  // Extract auth token and API URL from connection URI if provided
  const authToken = currentUri ? extractTokenFromUri(currentUri) : null;

  // Derive API base URL from the URI if provided
  const effectiveApiBaseUrl = getApiBaseUrlFromUri(currentUri ?? undefined, apiBaseUrl);

  // Log the effective API URL for debugging
  useEffect(() => {
    console.log("MorphikUI: Using API URL:", effectiveApiBaseUrl);
    console.log("MorphikUI: Auth token present:", !!authToken);
  }, [effectiveApiBaseUrl, authToken]);

  const initialChatMessages = loadChatMessages(currentChatId).map(m => ({
    id: generateUUID(),
    role: m.role as "user" | "assistant",
    content: m.content,
    createdAt: new Date(),
    experimental_customData: m.sources ? { sources: m.sources } : undefined,
  }));

  // Wrapper for section change to match expected type
  const handleSectionChange = (section: string) => {
    if (["documents", "search", "chat", "graphs", "agent", "connections"].includes(section)) {
      // Added "connections"
      setActiveSection(section as SectionType); // Use SectionType here
    }
  };

  return (
    <div className={cn("flex h-full w-full overflow-hidden")}>
      <Sidebar
        connectionUri={currentUri ?? undefined}
        isReadOnlyUri={isReadOnlyUri}
        onUriChange={handleUriChange}
        activeSection={activeSection}
        onSectionChange={handleSectionChange}
        isCollapsed={isSidebarCollapsed}
        setIsCollapsed={setIsSidebarCollapsed}
        onBackClick={onBackClick}
        chatList={chatList}
        currentChatId={currentChatId}
        onChatSelect={id => setCurrentChatId(id)}
        onNewChat={() => setCurrentChatId(createNewChat())}
      />

      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Render active section based on state */}
        {activeSection === "documents" && (
          <DocumentsSection
            key={`docs-${effectiveApiBaseUrl}-${initialFolder}`}
            apiBaseUrl={effectiveApiBaseUrl}
            authToken={authToken}
            initialFolder={initialFolder ?? undefined}
            setSidebarCollapsed={setIsSidebarCollapsed}
            onDocumentUpload={onDocumentUpload}
            onDocumentDelete={onDocumentDelete}
            onDocumentClick={onDocumentClick}
            onFolderCreate={onFolderCreate}
            onFolderClick={onFolderClick}
            onRefresh={undefined}
          />
        )}
        {activeSection === "search" && (
          <SearchSection
            key={`search-${effectiveApiBaseUrl}`}
            apiBaseUrl={effectiveApiBaseUrl}
            authToken={authToken}
            onSearchSubmit={onSearchSubmit}
          />
        )}
        {activeSection === "chat" && (
          <ChatSection
            key={`chat-${effectiveApiBaseUrl}`}
            apiBaseUrl={effectiveApiBaseUrl}
            authToken={authToken}
            chatId={currentChatId}
            initialMessages={initialChatMessages}
            onChatSubmit={onChatSubmit}
          />
        )}
        {activeSection === "agent" && (
          <AgentChatSection
            key={`agent-${effectiveApiBaseUrl}`}
            apiBaseUrl={effectiveApiBaseUrl}
            authToken={authToken}
            onAgentSubmit={onAgentSubmit}
          />
        )}
        {activeSection === "graphs" && (
          <GraphSection
            key={`graphs-${effectiveApiBaseUrl}`}
            apiBaseUrl={effectiveApiBaseUrl}
            authToken={authToken}
            onSelectGraph={onGraphClick}
            onGraphCreate={onGraphCreate}
            onGraphUpdate={onGraphUpdate}
          />
        )}
        {activeSection === "connections" && (
          <div className="h-full overflow-auto p-4 md:p-6">
            {/* Wrapper div for consistent padding and full height */}
            <ConnectorList apiBaseUrl={effectiveApiBaseUrl} authToken={authToken} />
          </div>
        )}
      </main>

      {/* Global alert system - integrated directly in the component */}
      <AlertSystem position="bottom-right" />
    </div>
  );
};

export default MorphikUI;
