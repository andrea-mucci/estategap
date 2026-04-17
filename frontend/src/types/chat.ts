export type VoiceInputState = "idle" | "listening" | "processing" | "error";

export type MessageRole = "user" | "assistant";

export type SessionStatus = "searching" | "confirming" | "confirmed" | "complete";

export type ChatConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export interface ChipItem {
  id: string;
  label: string;
}

export interface CarouselImage {
  listingId: string;
  src: string;
  alt: string;
  price: string;
  location: string;
}

export interface CriteriaField {
  key: string;
  label: string;
  value: string;
  inputType: "text" | "number" | "select";
  options?: string[];
}

export type MessageAttachment =
  | { type: "chips"; chips: ChipItem[] }
  | { type: "carousel"; images: CarouselImage[] }
  | { type: "criteria"; fields: CriteriaField[] }
  | { type: "listings"; count: number };

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  attachments: MessageAttachment[];
  timestamp: number;
  isStreaming: boolean;
}

export interface SessionState {
  messages: ChatMessage[];
  criteria: Record<string, string>;
  status: SessionStatus;
  streamingMessageId: string | null;
  snippetText: string;
  updatedAt: number;
}

export interface ChatStore {
  sessions: Map<string, SessionState>;
  activeSessionId: string | null;
  createSession: (sessionId?: string) => string;
  loadSession: (sessionId: string) => void;
  addMessage: (sessionId: string, message: ChatMessage) => void;
  startStreaming: (sessionId: string, messageId: string) => void;
  appendChunk: (sessionId: string, messageId: string, chunk: string) => void;
  endStreaming: (sessionId: string, messageId: string) => void;
  setAttachments: (
    sessionId: string,
    messageId: string,
    attachments: MessageAttachment[],
  ) => void;
  updateCriteria: (
    sessionId: string,
    patch: Partial<Record<string, string>>,
  ) => void;
  confirmSearch: (sessionId: string) => void;
}

export type IncomingWSMessage =
  | { type: "text_chunk"; sessionId: string; messageId: string; chunk: string }
  | { type: "stream_end"; sessionId: string; messageId: string }
  | {
      type: "attachments";
      sessionId: string;
      messageId: string;
      attachments: MessageAttachment[];
    }
  | { type: "criteria_update"; sessionId: string; criteria: Record<string, string> }
  | { type: "session_ready"; sessionId: string }
  | { type: "error"; code: string; message: string };

export type OutgoingWSMessage =
  | { type: "chat_message"; sessionId: string; content: string }
  | {
      type: "image_feedback";
      sessionId: string;
      listingId: string;
      action: "like" | "dislike";
    }
  | {
      type: "criteria_confirm";
      sessionId: string;
      criteria: Record<string, string>;
    };

export interface ChatSessionSummary {
  sessionId: string;
  snippetText: string;
  updatedAt: string;
  status: SessionStatus;
}

export interface ListingCard {
  listingId: string;
  title: string;
  price: number;
  currency: string;
  dealScore: number;
  photos: string[];
  bedrooms?: number;
  areaSqm?: number;
  location: string;
  latitude: number;
  longitude: number;
}

export interface ListingsPage {
  items: ListingCard[];
  nextCursor: string | null;
  total: number;
}

export type ListingsSort =
  | "price_asc"
  | "price_desc"
  | "deal_score_desc"
  | "date_desc";
