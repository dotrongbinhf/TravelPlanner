import React, { useState, ReactNode } from "react";
import { X } from "lucide-react";
import useEmblaCarousel from "embla-carousel-react";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PlaceCarouselItem {
  /** Unique key */
  id: string | number;
  /** Image URL to display */
  imageUrl?: string;
  /** Fallback image URL */
  fallbackImageUrl?: string;
}

export interface PlaceCarouselWidgetProps<T extends PlaceCarouselItem> {
  /** Section title shown in header */
  title: string;
  /** Subtitle shown below title */
  subtitle: string;
  /** Color theme identifier */
  theme?: "sky" | "rose" | "orange" | "emerald";
  /** Icon element shown left of title */
  headerIcon?: ReactNode;
  /** Items to display in the carousel */
  items: T[];
  /** Render a card in the carousel (receives item + isSelected) */
  renderCard: (item: T, index: number, onClick: () => void) => ReactNode;
  /** Render the expanded detail panel (receives item + onClose) */
  renderDetail: (item: T, onClose: () => void) => ReactNode;
  /** Called when no items available */
  emptyNode?: ReactNode;
  /** Called when detail panel is closed */
  onDetailClose?: () => void;
}

// ─── Theme map ────────────────────────────────────────────────────────────────

const THEMES = {
  sky:     { border: "border-sky-100",    bg: "bg-sky-50",     text: "text-sky-900",    subBorder: "border-sky-100"    },
  rose:    { border: "border-rose-100",   bg: "bg-rose-50",    text: "text-rose-900",   subBorder: "border-rose-100"   },
  orange:  { border: "border-orange-100", bg: "bg-orange-50",  text: "text-orange-900", subBorder: "border-orange-100" },
  emerald: { border: "border-emerald-100",bg: "bg-emerald-50", text: "text-emerald-900",subBorder: "border-emerald-100"},
};

// ─── Shared Component ─────────────────────────────────────────────────────────

export function PlaceCarouselWidget<T extends PlaceCarouselItem>({
  title,
  subtitle,
  theme = "sky",
  headerIcon,
  items,
  renderCard,
  renderDetail,
  emptyNode,
  onDetailClose,
}: PlaceCarouselWidgetProps<T>) {
  const [emblaRef] = useEmblaCarousel({
    align: "start",
    containScroll: "trimSnaps",
    dragFree: true,
  });

  const [selected, setSelected] = useState<T | null>(null);
  const t = THEMES[theme];

  if (items.length === 0) {
    return emptyNode ? <>{emptyNode}</> : null;
  }

  return (
    <div className={`w-full my-6 rounded-xl border ${t.border} shadow-sm bg-white`}>
      {/* Header */}
      <div className={`px-5 py-3 rounded-t-xl ${t.bg} ${t.text} border-b ${t.subBorder} flex items-center gap-3`}>
        {headerIcon && (
          <div className="w-8 h-8 overflow-hidden flex items-center justify-center shrink-0">
            {headerIcon}
          </div>
        )}
        <div>
          <h3 className="font-bold text-[15px] tracking-tight">{title}</h3>
          <p className={`text-[11px] ${t.text} font-medium`}>{subtitle}</p>
        </div>
      </div>

      <div className="p-5 bg-white rounded-b-xl">
        {/* Always mount carousel to preserve scroll position */}
        <div className={selected ? "hidden" : ""}>
          <div className="overflow-hidden" ref={emblaRef}>
            <div className="flex gap-4">
              {items.map((item, index) =>
                renderCard(item, index, () => setSelected(item))
              )}
            </div>
          </div>
        </div>

        {selected && (
          /* ── DETAIL VIEW ── */
          <div className="flex flex-col sm:flex-row bg-white border border-slate-200 rounded-2xl shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Close button layer */}
            <div className="relative flex-1 flex flex-col sm:flex-row w-full">
              <button
                className="absolute top-3 right-3 z-10 text-slate-400 hover:text-slate-600 transition-colors bg-white/80 rounded-full p-0.5"
                onClick={() => {
                  setSelected(null);
                  if (onDetailClose) onDetailClose();
                }}
              >
                <X className="w-5 h-5" />
              </button>
              {renderDetail(selected, () => {
                setSelected(null);
                if (onDetailClose) onDetailClose();
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
