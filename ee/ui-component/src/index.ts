"use client";

import MorphikUI from "../components/MorphikUI";
import { extractTokenFromUri, getApiBaseUrlFromUri } from "../lib/utils";
import { showAlert, showUploadAlert, removeAlert } from "../components/ui/alert-system";
import useChatHistory from "../hooks/useChatHistory";

export {
  MorphikUI,
  extractTokenFromUri,
  getApiBaseUrlFromUri,
  // Alert system helpers
  showAlert,
  showUploadAlert,
  removeAlert,
  useChatHistory,
};

// Export types
export type {
  MorphikUIProps,
  Document,
  SearchResult,
  ChatMessage,
  SearchOptions,
  QueryOptions,
} from "../components/types";
