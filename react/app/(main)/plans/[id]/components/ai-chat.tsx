"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  X,
  BotMessageSquare,
  Lightbulb,
  Compass,
  Wand2,
  Plus,
  MessageSquare,
  Check,
  Pencil,
  ChevronDown,
  Trash,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import WelcomeScreen, {
  HowToAskGuide,
  SamplePromptsPopup,
} from "./chats/welcome-screen";
import ChatMessages, { ChatMessage } from "./chats/chat-messages";
import ChatInput from "./chats/chat-input";
import PromptBuilder from "./chats/prompt-builder";
import { createPortal } from "react-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  getConversationsByPlanId,
  createConversation,
  updateConversationTitle,
  getMessagesByConversationId,
  addMessage,
  deleteConversation,
  markMessageApplied,
} from "@/api/aiChat";
import { Conversation, MessageRole } from "@/api/aiChat/types";
import { useParams } from "next/navigation";
import toast from "react-hot-toast";
import { useAgentStream } from "@/hooks/useAgentStream";
import { applyAIPlan } from "@/api/plan/plan";
import { Plan } from "@/types/plan";

interface AIChatProps {
  readonly planName: string;
  readonly planStartDate?: Date;
  readonly planEndDate?: Date;
  readonly onClose: () => void;
  readonly onPlanUpdated?: (plan: Plan) => void;
}

export default function AIChat({
  planName,
  planStartDate,
  planEndDate,
  onClose,
  onPlanUpdated,
}: AIChatProps) {
  const { id: planId } = useParams() as { id: string };

  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [input, setInput] = useState("");
  const [activePopup, setActivePopup] = useState<"guide" | "prompts" | null>(
    null,
  );
  const [showBuilder, setShowBuilder] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitleValue, setEditTitleValue] = useState("");
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isConversationsLoading, setIsConversationsLoading] = useState(true);

  const [backendMessages, setBackendMessages] = useState<any[]>([]);
  const [isMessagesLoading, setIsMessagesLoading] = useState(false);

  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const initializationAttempted = useRef(false); // Ref to prevent React StrictMode double-fire
  const streamingConversationIdRef = useRef<string | null>(null);

  // Agent streaming hook
  const {
    sendMessage: sendAgentMessage,
    streamState,
    isStreaming,
  } = useAgentStream();

  // Fetch Conversations
  const fetchConversations = useCallback(async () => {
    try {
      setIsConversationsLoading(true);
      const data = await getConversationsByPlanId(planId);
      setConversations(data);
      return data;
    } catch (error) {
      toast.error("Failed to load conversations");
      return [];
    } finally {
      setIsConversationsLoading(false);
    }
  }, [planId]);

  // Initial load
  useEffect(() => {
    const init = async () => {
      const data = await fetchConversations();

      // Auto-create only if no conversations exist AND we haven't already attempted it
      if (
        data.length === 0 &&
        !isCreatingConversation &&
        !initializationAttempted.current
      ) {
        initializationAttempted.current = true;
        handleStartNewConversation();
      } else if (data.length > 0 && !activeConversationId) {
        setActiveConversationId(data[0].id);
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId]);

  // Fetch Messages when activeConversationId changes
  useEffect(() => {
    if (!activeConversationId) return;
    const fetchMessages = async () => {
      try {
        setIsMessagesLoading(true);
        const msgs = await getMessagesByConversationId(activeConversationId);
        setBackendMessages(msgs);
      } catch (error) {
        toast.error("Failed to load messages");
      } finally {
        setIsMessagesLoading(false);
      }
    };
    fetchMessages();
  }, [activeConversationId]);

  // Handle Start New Conversation
  const handleStartNewConversation = async () => {
    try {
      setIsCreatingConversation(true);
      const newConv = await createConversation(planId, {
        planId,
        title: "New Conversation",
      });
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
    } catch (error) {
      toast.error("Failed to create conversation");
    } finally {
      setIsCreatingConversation(false);
    }
  };

  const handleSaveTitle = async () => {
    if (
      activeConversationId &&
      editTitleValue.trim() !== activeConversation?.title
    ) {
      try {
        const updatedTitle = editTitleValue.trim() || "Untitled";
        await updateConversationTitle(activeConversationId, {
          title: updatedTitle,
        });
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId ? { ...c, title: updatedTitle } : c,
          ),
        );
      } catch (error) {
        toast.error("Failed to update title");
      }
    }
    setIsEditingTitle(false);
  };

  const handleDeleteConversation = async () => {
    if (!conversationToDelete) return;

    try {
      await deleteConversation(conversationToDelete);

      const updatedConversations = conversations.filter(
        (c) => c.id !== conversationToDelete,
      );
      setConversations(updatedConversations);

      if (updatedConversations.length > 0) {
        if (activeConversationId === conversationToDelete) {
            setActiveConversationId(updatedConversations[0].id);
        }
      } else {
        setActiveConversationId(null);
        handleStartNewConversation();
      }
      toast.success("Conversation deleted");
    } catch (error) {
      toast.error("Failed to delete conversation");
    } finally {
      setConversationToDelete(null);
    }
  };

  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId,
  );

  // Convert backend messages to frontend ChatMessage format
  const messages: ChatMessage[] = backendMessages.map((m) => ({
    id: m.id,
    role: m.messageRole === MessageRole.Assistant ? "assistant" : "user",
    content: m.content,
    generatedPlanData: m.generatedPlanData || null,
    applyGeneratedPlanAt: m.applyGeneratedPlanAt || null,
  }));

  // When streaming is done but the message hasn't been saved to backend yet,
  // show the streamed content as a temporary message to avoid flicker
  if (
    !isStreaming &&
    streamState.isComplete &&
    streamState.streamedContent &&
    streamingConversationIdRef.current === activeConversationId &&
    !messages.some((m) => m.content === streamState.streamedContent)
  ) {
    messages.push({
      id: "streaming-complete",
      role: "assistant",
      content: streamState.streamedContent,
    });
  }

  const hasMessages = messages.length > 0;

  // When streaming completes, save the AI response to backend
  useEffect(() => {
    const targetConversationId = streamingConversationIdRef.current;
    if (
      streamState.isComplete &&
      streamState.streamedContent &&
      targetConversationId
    ) {
      const saveAIResponse = async () => {
        try {
          // Include generatedPlanData (apply_data) if available
          const applyData = streamState.structuredData
            ? (streamState.structuredData as any)?.apply_data
            : undefined;

          const newMsg = await addMessage(targetConversationId, {
            conversationId: targetConversationId,
            content: streamState.streamedContent,
            messageRole: MessageRole.Assistant,
            generatedPlanData: applyData ? JSON.stringify(applyData) : undefined,
          });
          // Only update messages list if still viewing the same conversation
          if (streamingConversationIdRef.current === activeConversationId) {
            setBackendMessages((prev) => [...prev, newMsg]);
          }
        } catch (e) {
          console.error("Failed to save AI response:", e);
        }
      };
      saveAIResponse();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamState.isComplete]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !activeConversationId) return;

      const userContent = text.trim();

      // Optimistic update
      const tempUserMsgId = Date.now().toString();
      setBackendMessages((prev) => [
        ...prev,
        {
          id: tempUserMsgId,
          conversationId: activeConversationId,
          content: userContent,
          messageRole: MessageRole.User,
        },
      ]);

      setInput("");
      setActivePopup(null);

      try {
        // Save user message to backend
        await addMessage(activeConversationId, {
          conversationId: activeConversationId,
          content: userContent,
          messageRole: MessageRole.User,
        });

        // Send to AI agent system via SignalR
        streamingConversationIdRef.current = activeConversationId;
        await sendAgentMessage(activeConversationId, userContent);
      } catch (error) {
        toast.error("Failed to send message");
        // Remove optimistic message
        setBackendMessages((prev) =>
          prev.filter((m) => m.id !== tempUserMsgId),
        );
      }
    },
    [activeConversationId, sendAgentMessage],
  );

  const handleSend = () => sendMessage(input);

  const handlePromptClick = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleBuilderGenerate = (prompt: string) => {
    setInput(prompt);
  };

  const handleOpenBuilder = () => {
    setActivePopup(null);
    setShowBuilder(true);
  };

  const handleSetPopup = (popup: "guide" | "prompts" | null) => {
    setActivePopup(popup);
  };

  return (
    <div className="w-full h-full flex flex-col rounded-lg border-2 border-gray-200 bg-white overflow-hidden relative">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0 bg-gray-50/50">
        <div className="flex items-center gap-3 min-w-0 pr-4 w-full">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0">
            <BotMessageSquare className="w-4 h-4 text-white" />
          </div>

          <div className="flex flex-col min-w-0 flex-1 justify-center">
            {isEditingTitle ? (
              <div className="flex items-center gap-2">
                <Input
                  autoFocus
                  value={editTitleValue}
                  onChange={(e) => setEditTitleValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSaveTitle();
                    if (e.key === "Escape") setIsEditingTitle(false);
                  }}
                  onBlur={handleSaveTitle}
                  className="h-7 text-sm font-semibold max-w-[200px]"
                />
              </div>
            ) : (
              <DropdownMenu>
                <div className="flex items-center gap-2 w-fit">
                  <DropdownMenuTrigger asChild>
                    <div className="flex items-center gap-1 cursor-pointer hover:bg-gray-100 rounded px-1 -ml-1 transition-colors">
                      <h3
                        className="text-sm font-semibold text-gray-800 truncate"
                        title="Click to switch conversation"
                      >
                        {activeConversation?.title || "AI Assistant"}
                      </h3>
                      <ChevronDown className="w-3 h-3 text-gray-400" />
                    </div>
                  </DropdownMenuTrigger>
                  <div className="flex items-center gap-1 group">
                    <button
                      onClick={() => {
                        setEditTitleValue(activeConversation?.title || "");
                        setIsEditingTitle(true);
                      }}
                      className="p-1 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity bg-yellow-400 hover:bg-yellow-500"
                      title="Rename conversation"
                    >
                      <Pencil className="w-3 h-3 text-white" />
                    </button>
                    <button
                      onClick={() => setConversationToDelete(activeConversationId)}
                      className="p-1 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity bg-red-100 hover:bg-red-200"
                      title="Delete conversation"
                    >
                      <Trash className="w-3 h-3 text-red-500" />
                    </button>
                  </div>
                </div>
                <DropdownMenuContent
                  align="start"
                  className="w-64 max-h-[300px] overflow-y-auto custom-scrollbar"
                >
                  {conversations.map((conv) => (
                    <DropdownMenuItem
                      key={conv.id}
                      onClick={() => setActiveConversationId(conv.id)}
                      className={cn(
                        "flex items-center justify-between cursor-pointer",
                        conv.id === activeConversationId && "bg-blue-50",
                      )}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <MessageSquare className="w-4 h-4 text-gray-400 flex-shrink-0" />
                        <span className="truncate text-sm">{conv.title}</span>
                      </div>
                      {conv.id === activeConversationId && (
                        <Check className="w-4 h-4 text-blue-600 flex-shrink-0" />
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            <p className="text-xs text-gray-500 truncate mt-0.5">{planName}</p>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleStartNewConversation}
            className="hidden sm:flex h-8 gap-1.5 rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50"
            title="New Conversation"
          >
            <Plus className="w-4 h-4" />
            <span className="text-xs font-medium">New Chat</span>
          </Button>
          <div className="w-px h-4 bg-gray-200 mx-1 hidden sm:block" />
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 rounded-lg hover:bg-gray-100 hover:text-gray-500"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {isMessagesLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : hasMessages || isStreaming ? (
        <ChatMessages
          messages={messages}
          streamingContent={
            isStreaming ? streamState.streamedContent : undefined
          }
          activeAgents={isStreaming ? streamState.activeAgents : undefined}
          completedAgents={isStreaming ? streamState.completedAgents : undefined}
          isStreaming={isStreaming}
          structuredData={streamState.structuredData}
          onApplyPlan={async (mode, messageId) => {
            // Resolve apply data: from specific message (DB) or from live stream
            let applyData: any = null;
            if (messageId && messageId !== "streaming") {
              const msg = backendMessages.find((m: any) => m.id === messageId);
              if (msg?.generatedPlanData) {
                try {
                  applyData = JSON.parse(msg.generatedPlanData);
                } catch {
                  toast.error("Invalid plan data");
                  return;
                }
              }
            }
            if (!applyData) {
              applyData = (streamState.structuredData as any)?.apply_data;
            }
            if (!applyData) {
              toast.error("No plan data available to apply");
              return;
            }
            try {
              const requestBody = {
                mode: mode === "CurrentPlan" ? 0 : 1,
                ...applyData,
              };
              const updatedPlan = await applyAIPlan(planId, requestBody);
              toast.success(
                mode === "CurrentPlan"
                  ? "Plan updated successfully!"
                  : "New plan created successfully!"
              );

              // Mark the message as applied in DB
              if (messageId && messageId !== "streaming") {
                try {
                  const updatedMsg = await markMessageApplied(messageId);
                  setBackendMessages((prev) =>
                    prev.map((m: any) =>
                      m.id === messageId ? { ...m, applyGeneratedPlanAt: updatedMsg.applyGeneratedPlanAt } : m
                    )
                  );
                } catch {
                  // Non-critical: apply succeeded, just couldn't mark timestamp
                  console.warn("Failed to mark message as applied");
                }
              }

              if (onPlanUpdated) {
                onPlanUpdated(updatedPlan);
              }
            } catch (error) {
              toast.error("Failed to apply plan. Please try again.");
              throw error; // Re-throw so ChatMessages can track failure
            }
          }}
        />
      ) : (
        <WelcomeScreen />
      )}

      {showBuilder &&
        document.getElementById("right-panel-container") &&
        createPortal(
          <div className="absolute inset-0 z-50 bg-white/60 backdrop-blur-sm flex items-center justify-center p-4 rounded-lg overflow-hidden animate-in fade-in duration-200">
            <div className="w-full h-full shadow-2xl rounded-lg overflow-hidden flex flex-col">
              <PromptBuilder
                onGenerate={handleBuilderGenerate}
                onClose={() => setShowBuilder(false)}
                defaultStartDate={planStartDate}
                defaultEndDate={planEndDate}
              />
            </div>
          </div>,
          document.getElementById("right-panel-container")!,
        )}

      <div className="flex-shrink-0 relative">
        {activePopup && (
          <div className="absolute bottom-full left-3 right-3 mb-1 rounded-xl border border-blue-100 bg-white shadow-lg overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200 z-10">
            <div className="flex items-center justify-between px-3 pt-2.5 pb-0">
              <div className="flex items-center gap-1.5">
                {activePopup === "guide" ? (
                  <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                ) : (
                  <Compass className="w-3.5 h-3.5 text-blue-500" />
                )}
                <span className="text-xs font-semibold text-gray-700">
                  {activePopup === "guide" ? "How to ask AI" : "Quick start"}
                </span>
              </div>
              <button
                onClick={() => handleSetPopup(null)}
                className="p-0.5 rounded hover:bg-gray-100 transition-colors"
              >
                <X className="w-3 h-3 text-gray-400" />
              </button>
            </div>
            {activePopup === "guide" ? (
              <HowToAskGuide onOpenBuilder={handleOpenBuilder} />
            ) : (
              <SamplePromptsPopup
                onPromptClick={handlePromptClick}
                onClose={() => handleSetPopup(null)}
              />
            )}
          </div>
        )}

        <div className="px-3 pt-1 pb-0 flex items-center justify-between">
          <div className="flex items-center">
            {/* Show + button here on small screens if needed, otherwise spacing */}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleStartNewConversation}
              className="sm:hidden h-8 w-8 rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50"
              title="New Conversation"
            >
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                handleSetPopup(activePopup === "prompts" ? null : "prompts")
              }
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-all",
                activePopup === "prompts"
                  ? "bg-blue-50 border-blue-200 text-blue-700"
                  : "bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50",
              )}
            >
              <Compass className="w-3.5 h-3.5" />
              Quick start
            </button>
            <button
              onClick={() =>
                handleSetPopup(activePopup === "guide" ? null : "guide")
              }
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-all",
                activePopup === "guide"
                  ? "bg-amber-50 border-amber-200 text-amber-700"
                  : "bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50",
              )}
            >
              <Lightbulb className="w-3.5 h-3.5" />
              How to ask
            </button>
            <button
              onClick={handleOpenBuilder}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-blue-200 bg-blue-50 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-all"
            >
              <Wand2 className="w-3.5 h-3.5" />
              Prompt Builder
            </button>
          </div>
        </div>

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={handleSend}
          showBuilderButton={!showBuilder}
          onOpenBuilder={handleOpenBuilder}
        />
      </div>

      <ConfirmDeleteModal
        open={!!conversationToDelete}
        onOpenChange={(open) => !open && setConversationToDelete(null)}
        title="Delete Conversation"
        description={`Are you sure you want to delete "${conversations.find((c) => c.id === conversationToDelete)?.title || "this conversation"}"? This action cannot be undone.`}
        onConfirm={handleDeleteConversation}
      />
    </div>
  );
}
