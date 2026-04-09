"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import {
  BotMessageSquare,
  Loader2,
  CheckCircle2,
  FilePlus2,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  generatedPlanData?: string | null;
  applyGeneratedPlanAt?: string | null;
}

interface ChatMessagesProps {
  readonly messages: ChatMessage[];
  readonly streamingContent?: string;
  readonly activeAgents?: string[];
  readonly completedAgents?: string[];
  readonly isStreaming?: boolean;
  readonly structuredData?: Record<string, unknown> | null;
  readonly onApplyPlan?: (
    mode: "CurrentPlan" | "NewPlan",
    messageId?: string,
  ) => Promise<void>;
}

// Map agent names to display labels
const AGENT_LABELS: Record<string, string> = {
  planner: "🧠 Planner",
  researcher: "🔍 Researcher",
  dotnet_integration: "📡 Data Fetcher",
  response: "📝 Composing Response",
  orchestrator: "🧠 Orchestrator",
  flight_agent: "✈️ Flight Agent",
  hotel_agent: "🏨 Hotel Agent",
  attraction_agent: "🎪 Attraction Agent",
  restaurant_agent: "🍽️ Restaurant Agent",
  preparation_agent: "🎒 Preparation Agent",
  itinerary_agent: "📅 Itinerary Agent",
  synthesize: "📝 Composing Response",
};

// Reusable markdown components config
const markdownComponents = {
  h1: ({ node, ...props }: any) => (
    <h1 className="text-2xl font-bold mt-4 mb-2" {...props} />
  ),
  h2: ({ node, ...props }: any) => (
    <h2 className="text-xl font-bold mt-4 mb-2" {...props} />
  ),
  h3: ({ node, ...props }: any) => (
    <h3 className="text-lg font-bold mt-3 mb-2" {...props} />
  ),
  p: ({ node, ...props }: any) => <p className="mb-2 last:mb-0" {...props} />,
  ul: ({ node, ...props }: any) => (
    <ul className="list-disc pl-5 mb-2 space-y-1" {...props} />
  ),
  ol: ({ node, ...props }: any) => (
    <ol className="list-decimal pl-5 mb-2 space-y-1" {...props} />
  ),
  li: ({ node, ...props }: any) => (
    <li className="leading-relaxed" {...props} />
  ),
  strong: ({ node, ...props }: any) => (
    <strong className="font-semibold" {...props} />
  ),
  blockquote: ({ node, ...props }: any) => (
    <blockquote
      className="border-l-4 border-blue-500 pl-3 italic text-gray-600 bg-blue-50/50 py-1 my-2"
      {...props}
    />
  ),
};

function formatAppliedAt(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export default function ChatMessages({
  messages,
  streamingContent,
  activeAgents,
  completedAgents,
  isStreaming,
  structuredData,
  onApplyPlan,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  const isInitialLoadRef = useRef(true);
  const prevMsgCountRef = useRef(messages.length);

  const [applyingMessageId, setApplyingMessageId] = useState<string | null>(
    null,
  );
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [confirmMessageId, setConfirmMessageId] = useState<string | null>(null);

  const lastUserMsgId = [...messages].reverse().find(m => m.role === "user")?.id;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const scrollToLastUserMsg = useCallback(() => {
    if (lastUserMessageRef.current) {
      lastUserMessageRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      scrollToBottom();
    }
  }, [scrollToBottom]);

  useEffect(() => {
    if (isInitialLoadRef.current && messages.length > 0) {
      setTimeout(scrollToLastUserMsg, 100);
      isInitialLoadRef.current = false;
      prevMsgCountRef.current = messages.length;
      return;
    }

    if (messages.length > prevMsgCountRef.current || isStreaming || (streamingContent && streamingContent.length > 0)) {
      scrollToBottom();
    }
    
    prevMsgCountRef.current = messages.length;
  }, [messages.length, isStreaming, streamingContent, scrollToBottom, scrollToLastUserMsg]);

  // Check if any DB-loaded message already has generatedPlanData
  const hasDbApplyData = messages.some((m) => m.generatedPlanData);

  const streamingHasApplyData =
    !isStreaming &&
    structuredData &&
    (structuredData as any)?.apply_data &&
    !hasDbApplyData;

  const handleApply = async (
    mode: "CurrentPlan" | "NewPlan",
    messageId?: string,
  ) => {
    if (!onApplyPlan) return;
    setApplyingMessageId(messageId || "streaming");
    try {
      await onApplyPlan(mode, messageId);
    } catch {
      // Error handled by parent
    } finally {
      setApplyingMessageId(null);
    }
  };

  const handleCurrentPlanClick = (messageId?: string) => {
    setConfirmMessageId(messageId || null);
    setShowConfirmDialog(true);
  };

  const handleConfirmReplace = () => {
    setShowConfirmDialog(false);
    handleApply("CurrentPlan", confirmMessageId || undefined);
  };

  const renderApplyButton = (
    messageId: string,
    applyGeneratedPlanAt?: string | null,
  ) => {
    const isApplying = applyingMessageId === messageId;
    return (
      <div className="flex justify-start pl-8 mt-1.5 animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div className="flex items-center gap-2 p-3 rounded-xl bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200">
          {applyGeneratedPlanAt ? (
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-xs text-emerald-700 font-medium">
                Applied at {formatAppliedAt(applyGeneratedPlanAt)}
              </span>
              <span className="text-xs text-gray-400">·</span>
            </div>
          ) : (
            <span className="text-xs text-emerald-700 font-medium">
              Plan ready to apply
            </span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                disabled={isApplying}
                className="h-7 px-3 text-xs font-semibold bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-600 hover:to-green-700 text-white rounded-lg shadow-sm"
              >
                {isApplying ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    Applying...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    {applyGeneratedPlanAt ? "Re-apply" : "Apply Plan"}
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              <DropdownMenuItem
                onClick={() => handleCurrentPlanClick(messageId)}
                className="cursor-pointer"
              >
                <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
                <div>
                  <div className="text-sm font-medium">Apply to this plan</div>
                  <div className="text-xs text-gray-500">
                    Replace current plan data
                  </div>
                </div>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleApply("NewPlan", messageId)}
                className="cursor-pointer"
              >
                <FilePlus2 className="w-4 h-4 mr-2 text-blue-600" />
                <div>
                  <div className="text-sm font-medium">Create new plan</div>
                  <div className="text-xs text-gray-500">
                    Keep current plan unchanged
                  </div>
                </div>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
      {messages.map((msg) => (
        <div key={msg.id} ref={msg.id === lastUserMsgId ? lastUserMessageRef : null}>
          <div
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
                <BotMessageSquare className="w-3 h-3 text-white" />
              </div>
            )}
            <div
              className={cn(
                "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words",
                msg.role === "user"
                  ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-md"
                  : "bg-gray-100 text-gray-800 rounded-bl-md",
              )}
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>

          {/* Per-message Apply button — for messages loaded from DB */}
          {msg.role === "assistant" &&
            msg.generatedPlanData &&
            renderApplyButton(msg.id, msg.applyGeneratedPlanAt)}
        </div>
      ))}

      {/* Streaming indicator & content */}
      {isStreaming && (
        <div className="flex justify-start">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
            <BotMessageSquare className="w-3 h-3 text-white" />
          </div>
          <div className="max-w-[80%] space-y-2">
            {/* Agent status badge */}
            {(activeAgents?.length! > 0 || completedAgents?.length! > 0) && (
              <div className="flex flex-col gap-1.5 mt-1 border-l-2 pl-3 border-blue-200">
                {completedAgents?.map((agentName) => (
                  <div
                    key={agentName}
                    className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span>
                      {AGENT_LABELS[agentName] || agentName} completed
                    </span>
                  </div>
                ))}
                {activeAgents?.map((agentName) => (
                  <div
                    key={agentName}
                    className="flex items-center gap-1.5 text-xs text-blue-600 font-medium"
                  >
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span className="animate-pulse">
                      {AGENT_LABELS[agentName] || agentName} running...
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Streamed text content */}
            {streamingContent ? (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words bg-gray-100 text-gray-800">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {streamingContent}
                </ReactMarkdown>
                <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm" />
              </div>
            ) : (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 bg-gray-100">
                <div className="flex items-center gap-1">
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Apply button for streaming result (not yet saved to DB) */}
      {streamingHasApplyData && renderApplyButton("streaming")}

      {/* Confirm replace dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Replace current plan?
            </DialogTitle>
            <DialogDescription>
              This will <strong>replace all existing data</strong> in your
              current plan (itinerary, budget, packing lists, notes) with the
              AI-generated plan. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmReplace}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Yes, replace plan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div ref={messagesEndRef} />
    </div>
  );
}
