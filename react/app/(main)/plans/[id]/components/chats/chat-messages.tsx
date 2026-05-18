"use client";

import { useEffect, useRef, useCallback, useMemo, useState } from "react";
import {
  BotMessageSquare,
  Loader2,
  CheckCircle2,
  FilePlus2,
  AlertTriangle,
  Circle,
  X,
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
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { CheckIcon } from "@/components/ui/check";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { HotelWidget } from "./widgets/HotelWidget";
import { FlightWidget } from "./widgets/FlightWidget";
import { AttractionWidget } from "./widgets/AttractionWidget";
import { RestaurantWidget } from "./widgets/RestaurantWidget";
import { useItineraryContext, type ChatPlace } from "@/contexts/ItineraryContext";
import { ApplySection } from "@/api/aiChat/types";

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
    messageId: string,
    sections: ApplySection[],
  ) => Promise<void>;
}

type ApplySectionKey = "itinerary" | "budget" | "packing" | "notes";
type MapWidgetSource = "hotel" | "attraction" | "restaurant";
type ChatWidgetKind = MapWidgetSource | "flight";

const CHAT_WIDGETS: Array<{
  tag: string;
  kind: ChatWidgetKind;
  dataKey: string;
  source?: MapWidgetSource;
}> = [
  {
    tag: "[HOTEL_UI_WIDGET]",
    kind: "hotel",
    dataKey: "hotel_agent",
    source: "hotel",
  },
  {
    tag: "[FLIGHT_UI_WIDGET]",
    kind: "flight",
    dataKey: "flight_agent",
  },
  {
    tag: "[ATTRACTION_UI_WIDGET]",
    kind: "attraction",
    dataKey: "attraction_agent",
    source: "attraction",
  },
  {
    tag: "[RESTAURANT_UI_WIDGET]",
    kind: "restaurant",
    dataKey: "restaurant_agent",
    source: "restaurant",
  },
];

type WidgetOccurrence = {
  configIndex: number;
  widgetIndex: number;
};

type MapWidgetEntry = {
  key: string;
  source: MapWidgetSource;
  places: ChatPlace[];
};

const getWidgetOccurrences = (content: string): WidgetOccurrence[] => {
  const occurrences: WidgetOccurrence[] = [];
  const counters = new Map<string, number>();
  let remaining = content;

  while (remaining.length > 0) {
    let earliest = -1;
    let earliestPos = Infinity;

    for (let i = 0; i < CHAT_WIDGETS.length; i++) {
      const pos = remaining.indexOf(CHAT_WIDGETS[i].tag);
      if (pos !== -1 && pos < earliestPos) {
        earliest = i;
        earliestPos = pos;
      }
    }

    if (earliest === -1) break;

    const kind = CHAT_WIDGETS[earliest].kind;
    const widgetIndex = counters.get(kind) || 0;
    counters.set(kind, widgetIndex + 1);
    occurrences.push({ configIndex: earliest, widgetIndex });
    remaining = remaining.substring(
      earliestPos + CHAT_WIDGETS[earliest].tag.length,
    );
  }

  return occurrences;
};

const getLocation = (item: any): ChatPlace["location"] | null => {
  const coordinates =
    item?.db_data?.location?.coordinates ||
    item?._location?.coordinates ||
    item?.location?.coordinates;
  if (Array.isArray(coordinates) && coordinates.length === 2) {
    return { lat: coordinates[1], lng: coordinates[0] };
  }

  const lat = item?._location?.lat ?? item?.location?.lat;
  const lng = item?._location?.lng ?? item?.location?.lng;
  if (lat != null && lng != null) {
    return { lat, lng };
  }

  return null;
};

const extractHotelPlaces = (data: any): ChatPlace[] => {
  const places: ChatPlace[] = [];
  data?.segments?.forEach((segment: any) => {
    const hotels = [
      {
        ...segment,
        id: segment.recommend_hotel_name,
        name: segment.recommend_hotel_name,
        placeId:
          segment.recommend_hotel_placeId ||
          segment.placeId ||
          segment.place_id,
      },
      ...(segment.alternatives || []).map((alt: any, idx: number) => ({
        ...alt,
        id: alt.id || alt.name || `hotel-alt-${idx}`,
      })),
    ];

    hotels.forEach((hotel: any) => {
      const location = getLocation(hotel);
      const name = hotel.name || hotel.recommend_hotel_name;
      if (!location || !name) return;
      places.push({
        id: String(hotel.id || name),
        placeId:
          hotel.placeId ||
          hotel.place_id ||
          hotel.recommend_hotel_placeId,
        name,
        location,
        source: "hotel",
      });
    });
  });
  return places;
};

const extractAttractionPlaces = (data: any): ChatPlace[] => {
  const places: ChatPlace[] = [];
  data?.segments?.forEach((segment: any) => {
    (segment.attractions || []).forEach((attraction: any, idx: number) => {
      const location = getLocation(attraction);
      const name = attraction.name || attraction.recommend_attraction_name;
      if (!location || !name) return;
      places.push({
        id: String(
          attraction.id ||
            attraction.place_id ||
            attraction.placeId ||
            name ||
            `attraction-${idx}`,
        ),
        placeId: attraction.place_id || attraction.placeId,
        name,
        location,
        source: "attraction",
      });
    });
  });
  return places;
};

const extractRestaurantPlaces = (data: any): ChatPlace[] => {
  const places: ChatPlace[] = [];
  data?.meals?.forEach((meal: any, mealIdx: number) => {
    const restaurants = [
      { ...meal, id: meal.id || meal.place_id || meal.name || `meal-${mealIdx}` },
      ...(meal.alternatives || [])
        .filter((alt: any) => typeof alt !== "string")
        .map((alt: any, altIdx: number) => ({
          ...alt,
          id: alt.id || alt.place_id || alt.name || `restaurant-alt-${mealIdx}-${altIdx}`,
        })),
    ];

    restaurants.forEach((restaurant: any) => {
      const location = getLocation(restaurant);
      const name = restaurant.name || restaurant.recommend_restaurant_name;
      if (!location || !name) return;
      places.push({
        id: String(restaurant.id || name),
        placeId: restaurant.place_id || restaurant.placeId,
        name,
        location,
        source: "restaurant",
      });
    });
  });
  return places;
};

const extractWidgetPlaces = (
  source: MapWidgetSource,
  data: any,
): ChatPlace[] => {
  if (source === "hotel") return extractHotelPlaces(data);
  if (source === "attraction") return extractAttractionPlaces(data);
  return extractRestaurantPlaces(data);
};

const buildMapWidgetEntries = (
  content: string,
  ownerId: string,
  structuredData?: Record<string, unknown> | null,
): MapWidgetEntry[] => {
  if (!structuredData) return [];
  return getWidgetOccurrences(content)
    .map((occurrence) => {
      const config = CHAT_WIDGETS[occurrence.configIndex];
      if (!config.source) return null;
      const data = (structuredData as any)?.[config.dataKey];
      const places = extractWidgetPlaces(config.source, data);
      if (places.length === 0) return null;
      return {
        key: `${ownerId}:${config.kind}:${occurrence.widgetIndex}`,
        source: config.source,
        places,
      };
    })
    .filter(Boolean) as MapWidgetEntry[];
};

const OVERVIEW_SECTION_META = {
  key: "overview",
  enumValue: ApplySection.Overview,
  label: "Overview",
};

const APPLY_SECTION_META: Array<{
  key: ApplySectionKey;
  enumValue: ApplySection;
  label: string;
}> = [
  { key: "itinerary", enumValue: ApplySection.Itinerary, label: "Itinerary" },
  { key: "budget", enumValue: ApplySection.Budget, label: "Budget" },
  { key: "packing", enumValue: ApplySection.Packing, label: "Packing" },
  { key: "notes", enumValue: ApplySection.Notes, label: "Notes" },
];

const hasSectionData = (section: any) => {
  const data = section?.data;
  if (Array.isArray(data)) return data.length > 0;
  if (data && typeof data === "object") return Object.keys(data).length > 0;
  return Boolean(data);
};

const getAvailableApplySections = (applyData: any) =>
  APPLY_SECTION_META.filter((section) =>
    hasSectionData(applyData?.sections?.[section.key]),
  );

const getChangedApplySections = (applyData: any) =>
  getAvailableApplySections(applyData).filter(
    (section) => applyData?.sections?.[section.key]?.is_apply,
  );

const hasOverviewData = (applyData: any) =>
  hasSectionData(applyData?.sections?.overview) ||
  hasSectionData({ data: applyData?.plan_context });

const formatApplySectionEnums = (
  sections: ApplySection[],
  fallback: string,
) => {
  const labels = [
    ...(sections.includes(ApplySection.Overview)
      ? [OVERVIEW_SECTION_META]
      : []),
    ...APPLY_SECTION_META.filter((section) =>
      sections.includes(section.enumValue),
    ),
  ];
  return formatSectionLabels(labels, fallback);
};

const formatSectionLabels = (
  sections: Array<{ label: string }>,
  fallback: string,
) =>
  sections.length
    ? sections.map((section) => section.label).join(", ")
    : fallback;

// Map agent names to display labels
const AGENT_LABELS: Record<string, string> = {
  intent: "🎯 Recognizing Intent",
  orchestrator: "🧠 Planning Overview",
  flight_agent: "✈️ Searching Flights",
  hotel_agent: "🏨 Searching Hotels",
  attraction_agent: "🎪 Finding Attractions",
  restaurant_agent: "🍽️ Finding Restaurants",
  preparation_agent: "🎒 Preparing Trip Essentials",
  itinerary_agent: "📅 Building Itinerary",
  weather: "🌤️ Checking Weather",
  synthesize: "📝 Composing Response",
  select_apply: "✅ Finalizing Selections",
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
  table: ({ node, ...props }: any) => (
    <div className="overflow-x-auto my-4 w-full rounded-xl border border-sky-100 shadow-sm bg-white">
      <table
        className="w-full text-sm text-left whitespace-nowrap"
        {...props}
      />
    </div>
  ),
  thead: ({ node, ...props }: any) => (
    <thead
      className="bg-sky-50 text-sky-900 border-b border-sky-100"
      {...props}
    />
  ),
  th: ({ node, ...props }: any) => (
    <th className="px-4 py-3 font-semibold" {...props} />
  ),
  td: ({ node, ...props }: any) => (
    <td className="px-4 py-2 border-t border-sky-50" {...props} />
  ),
  tr: ({ node, ...props }: any) => (
    <tr className="hover:bg-sky-50/50 transition-colors" {...props} />
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
  const [activeMapWidgets, setActiveMapWidgets] = useState<
    Partial<Record<MapWidgetSource, string>>
  >({});

  const toggleMapWidget = useCallback(
    (source: MapWidgetSource, widgetKey: string) => {
      setActiveMapWidgets((prev) => ({
        ...prev,
        [source]: prev[source] === widgetKey ? undefined : widgetKey,
      }));
    },
    [],
  );

  // Helper to split message and render widgets — supports MULTIPLE widgets in one message
  const renderWidget = (
    configIndex: number,
    sd: any,
    widgetKey: string,
  ) => {
    const config = CHAT_WIDGETS[configIndex];
    const data = sd?.[config.dataKey];
    const mapPlaces = config.source
      ? extractWidgetPlaces(config.source, data)
      : [];
    const mapProps =
      config.source && mapPlaces.length > 0
        ? {
            mapVisible: activeMapWidgets[config.source] === widgetKey,
            onToggleMap: () => toggleMapWidget(config.source!, widgetKey),
          }
        : {};

    if (config.kind === "hotel") {
      return <HotelWidget data={data} {...mapProps} />;
    }
    if (config.kind === "flight") {
      return <FlightWidget data={data} />;
    }
    if (config.kind === "attraction") {
      return <AttractionWidget data={data} {...mapProps} />;
    }
    return <RestaurantWidget data={data} {...mapProps} />;
  };

  const renderMessageWithWidgets = (
    content: string,
    msgStructuredData?: Record<string, unknown> | null,
    messageId = "streaming",
  ) => {
    // Check if ANY widget tag exists
    const hasWidget = CHAT_WIDGETS.some((w) => content.includes(w.tag));
    if (!hasWidget) {
      return (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {content}
        </ReactMarkdown>
      );
    }

    // Split content by ALL widget tags, preserving order
    type Segment =
      | { type: "text"; content: string }
      | { type: "widget"; tagIndex: number; widgetIndex: number };
    const segments: Segment[] = [];
    const widgetCounters = new Map<ChatWidgetKind, number>();
    let remaining = content;

    while (remaining.length > 0) {
      // Find the earliest widget tag in remaining
      let earliest = -1;
      let earliestPos = Infinity;
      for (let i = 0; i < CHAT_WIDGETS.length; i++) {
        const pos = remaining.indexOf(CHAT_WIDGETS[i].tag);
        if (pos !== -1 && pos < earliestPos) {
          earliestPos = pos;
          earliest = i;
        }
      }

      if (earliest === -1) {
        // No more widgets, push remaining text
        if (remaining.trim())
          segments.push({ type: "text", content: remaining });
        break;
      }

      // Push text before the widget
      const textBefore = remaining.substring(0, earliestPos);
      if (textBefore.trim())
        segments.push({ type: "text", content: textBefore });

      // Push the widget
      const widgetKind = CHAT_WIDGETS[earliest].kind;
      const widgetIndex = widgetCounters.get(widgetKind) || 0;
      widgetCounters.set(widgetKind, widgetIndex + 1);
      segments.push({ type: "widget", tagIndex: earliest, widgetIndex });

      // Advance past the tag
      remaining = remaining.substring(
        earliestPos + CHAT_WIDGETS[earliest].tag.length,
      );
    }

    return (
      <div className="flex flex-col">
        {segments.map((seg, idx) =>
          seg.type === "text" ? (
            <ReactMarkdown
              key={idx}
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {seg.content}
            </ReactMarkdown>
          ) : (
            <div key={idx}>
              {renderWidget(
                seg.tagIndex,
                msgStructuredData,
                `${messageId}:${CHAT_WIDGETS[seg.tagIndex].kind}:${seg.widgetIndex}`,
              )}
            </div>
          ),
        )}
      </div>
    );
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  const isInitialLoadRef = useRef(true);
  const prevMsgCountRef = useRef(messages.length);

  const [applyingMessageId, setApplyingMessageId] = useState<string | null>(
    null,
  );
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [confirmMessageId, setConfirmMessageId] = useState<string | null>(null);
  const [confirmSections, setConfirmSections] = useState<ApplySection[]>([]);
  const [showCustomDialog, setShowCustomDialog] = useState(false);
  const [customMessageId, setCustomMessageId] = useState<string | null>(null);
  const [customSections, setCustomSections] = useState<ApplySection[]>([]);
  const [customAvailableSections, setCustomAvailableSections] = useState<
    ReturnType<typeof getAvailableApplySections>
  >([]);

  const { setChatPlaces } = useItineraryContext();

  const persistedWidgetEntries = useMemo(() => {
    return messages.flatMap((message) => {
      if (!message.generatedPlanData) return [];
      try {
        const parsed = JSON.parse(message.generatedPlanData);
        return buildMapWidgetEntries(message.content, message.id, parsed);
      } catch {
        return [];
      }
    });
  }, [messages]);

  const streamingWidgetEntries = useMemo(() => {
    if (!isStreaming || !streamingContent || !structuredData) return [];
    return buildMapWidgetEntries(
      streamingContent,
      "streaming",
      structuredData,
    );
  }, [isStreaming, streamingContent, structuredData]);

  const allMapWidgetEntries = useMemo(
    () => [...persistedWidgetEntries, ...streamingWidgetEntries],
    [persistedWidgetEntries, streamingWidgetEntries],
  );

  const lastUserMsgId = [...messages]
    .reverse()
    .find((m) => m.role === "user")?.id;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const scrollToLastUserMsg = useCallback(() => {
    if (lastUserMessageRef.current) {
      lastUserMessageRef.current.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    } else {
      scrollToBottom();
    }
  }, [scrollToBottom]);

  useEffect(() => {
    const visiblePlaces = allMapWidgetEntries
      .filter((entry) => activeMapWidgets[entry.source] === entry.key)
      .flatMap((entry) => entry.places);
    setChatPlaces(visiblePlaces);
  }, [activeMapWidgets, allMapWidgetEntries, setChatPlaces]);

  useEffect(() => {
    if (isInitialLoadRef.current && messages.length > 0) {
      setTimeout(scrollToLastUserMsg, 100);
      isInitialLoadRef.current = false;
      prevMsgCountRef.current = messages.length;
      return;
    }

    if (
      messages.length > prevMsgCountRef.current ||
      isStreaming ||
      (streamingContent && streamingContent.length > 0)
    ) {
      scrollToBottom();
    }

    prevMsgCountRef.current = messages.length;
  }, [
    messages.length,
    isStreaming,
    streamingContent,
    scrollToBottom,
    scrollToLastUserMsg,
  ]);

  const handleApply = async (messageId: string, sections: ApplySection[]) => {
    if (!onApplyPlan) return;
    const sectionsWithOverview = Array.from(
      new Set([ApplySection.Overview, ...sections]),
    );
    setApplyingMessageId(messageId);
    try {
      await onApplyPlan(messageId, sectionsWithOverview);
    } catch {
      // Error handled by parent
    } finally {
      setApplyingMessageId(null);
    }
  };

  const handleApplyChangesClick = (messageId: string, applyData: any) => {
    const changedSections = getChangedApplySections(applyData);
    setConfirmMessageId(messageId || null);
    setConfirmSections([
      ...(hasOverviewData(applyData) ? [ApplySection.Overview] : []),
      ...changedSections.map((s) => s.enumValue),
    ]);
    setShowConfirmDialog(true);
  };

  const handleConfirmReplace = () => {
    setShowConfirmDialog(false);
    if (confirmMessageId) {
      handleApply(confirmMessageId, confirmSections);
    }
  };

  const handleCustomSectionsClick = (messageId: string, applyData: any) => {
    const availableSections = getAvailableApplySections(applyData);
    const changedSections = getChangedApplySections(applyData);
    setCustomMessageId(messageId);
    setCustomAvailableSections(availableSections);
    setCustomSections([
      ...(hasOverviewData(applyData) ? [ApplySection.Overview] : []),
      ...changedSections.map((s) => s.enumValue),
    ]);
    setShowCustomDialog(true);
  };

  const handleToggleCustomSection = (section: ApplySection) => {
    setCustomSections((prev) =>
      prev.includes(section)
        ? prev.filter((current) => current !== section)
        : [...prev, section],
    );
  };

  const handleApplyCustomSections = () => {
    setShowCustomDialog(false);
    if (customMessageId) {
      handleApply(customMessageId, customSections);
    }
  };

  const renderApplyButton = (
    messageId: string,
    applyGeneratedPlanAt?: string | null,
    applyData?: any,
  ) => {
    const isApplying = applyingMessageId === messageId;
    const changedSections = getChangedApplySections(applyData);
    const availableSections = getAvailableApplySections(applyData);
    const hasChangedSections = changedSections.length > 0;
    const hasAvailableSections = availableSections.length > 0;
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
            <DropdownMenuContent align="start" className="w-56">
              <DropdownMenuItem
                onClick={() => handleApplyChangesClick(messageId, applyData)}
                disabled={!hasChangedSections}
                className="cursor-pointer"
              >
                <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-600" />
                <div>
                  <div className="text-sm font-medium">Apply Changes Only</div>
                  <div className="text-xs text-gray-500">
                    Apply to{" "}
                    {formatSectionLabels(changedSections, "no sections")}
                  </div>
                </div>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleCustomSectionsClick(messageId, applyData)}
                disabled={!hasAvailableSections}
                className="cursor-pointer"
              >
                <FilePlus2 className="w-4 h-4 mr-2 text-blue-600" />
                <div>
                  <div className="text-sm font-medium">
                    Apply Custom Sections
                  </div>
                  <div className="text-xs text-gray-500">
                    Choose which sections to apply
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
      {messages.map((msg) => {
        let parsedData: any = null;
        if (msg.generatedPlanData) {
          try {
            parsedData = JSON.parse(msg.generatedPlanData);
          } catch (e) {}
        }

        return (
          <div
            key={msg.id}
            ref={msg.id === lastUserMsgId ? lastUserMessageRef : null}
          >
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
                    ? "bg-gradient-to-r from-sky-500 to-blue-500 text-white shadow-sm rounded-br-md"
                    : "bg-white text-gray-800 border border-sky-100 shadow-sm rounded-bl-md",
                )}
              >
                {renderMessageWithWidgets(
                  msg.content,
                  parsedData || structuredData,
                  msg.id,
                )}
              </div>
            </div>

            {/* Per-message Apply button — for messages with plan data */}
            {msg.role === "assistant" &&
              parsedData?.apply_data &&
              renderApplyButton(
                msg.id,
                msg.applyGeneratedPlanAt,
                parsedData.apply_data,
              )}
          </div>
        );
      })}

      {/* Streaming indicator & content */}
      {isStreaming && (
        <div className="flex justify-start">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
            <BotMessageSquare className="w-3 h-3 text-white" />
          </div>
          <div className="max-w-[80%] space-y-2">
            {/* Agent status badge */}
            {((activeAgents?.length ?? 0) > 0 ||
              (completedAgents?.length ?? 0) > 0) && (
              <div className="flex flex-col gap-1.5 mt-1 border-l-2 pl-3 border-blue-200">
                {completedAgents?.map((agentName) => (
                  <div
                    key={agentName}
                    className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span>{AGENT_LABELS[agentName] || agentName}</span>
                  </div>
                ))}
                {activeAgents?.map((agentName) => (
                  <div
                    key={agentName}
                    className="flex items-center gap-1.5 text-xs text-blue-600 font-medium"
                  >
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span className="animate-pulse">
                      {AGENT_LABELS[agentName] || agentName}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Streamed text content */}
            {streamingContent ? (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words bg-white text-gray-800 border border-sky-100 shadow-sm">
                {renderMessageWithWidgets(
                  streamingContent,
                  structuredData,
                  "streaming",
                )}
                <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm" />
              </div>
            ) : (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 bg-white border border-sky-100 shadow-sm">
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

      {/* Confirm apply dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent className="sm:max-w-[500px] [&>button]:hidden">
          <DialogHeader className="relative">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-amber-100 rounded-full">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <DialogTitle className="text-lg font-semibold text-gray-900">
                Apply changed sections?
              </DialogTitle>
            </div>
            <DialogDescription className="text-gray-700 mt-2 font-medium">
              This will apply changes to{" "}
              <strong>
                {formatApplySectionEnums(confirmSections, "no sections")}
              </strong>
              . This action will replace the current plan data for these
              sections.
            </DialogDescription>
            <DialogClose asChild>
              <button
                className="absolute -top-2 -right-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors duration-200 cursor-pointer"
                aria-label="Close"
              >
                <X className="w-5 h-5 text-gray-500 hover:text-gray-700" />
              </button>
            </DialogClose>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
              className="bg-gray-50 hover:bg-gray-200"
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmReplace}
              disabled={confirmSections.length === 0}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              Apply changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showCustomDialog} onOpenChange={setShowCustomDialog}>
        <DialogContent className="sm:max-w-[500px] [&>button]:hidden">
          <DialogHeader className="relative">
            <DialogTitle>Apply custom sections</DialogTitle>
            <DialogDescription>
              Select which sections to apply to your plan.
            </DialogDescription>
            <DialogClose asChild>
              <button
                className="absolute -top-2 -right-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors duration-200 cursor-pointer"
                aria-label="Close"
              >
                <X className="w-5 h-5 text-gray-500 hover:text-gray-700" />
              </button>
            </DialogClose>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            {customAvailableSections.map((section) => {
              const isChecked = customSections.includes(section.enumValue);
              return (
                <div
                  key={section.key}
                  className="flex items-center gap-3 rounded-lg p-3 bg-gray-100 cursor-pointer hover:bg-gray-200 transition-colors"
                  onClick={() => handleToggleCustomSection(section.enumValue)}
                >
                  {isChecked ? (
                    <CheckIcon
                      className="text-white bg-[#2B7FFF] rounded-full p-1"
                      size={10}
                      animateOnMount={true}
                      disableHover={true}
                    />
                  ) : (
                    <Circle size={18} className="text-gray-400" />
                  )}
                  <span className="font-medium text-sm text-gray-800 flex-1">
                    {section.label}
                  </span>
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCustomDialog(false)}
              className="bg-gray-50 hover:bg-gray-200"
            >
              Cancel
            </Button>
            <Button
              onClick={handleApplyCustomSections}
              disabled={customSections.length === 0}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              Apply selected sections
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div ref={messagesEndRef} />
    </div>
  );
}
