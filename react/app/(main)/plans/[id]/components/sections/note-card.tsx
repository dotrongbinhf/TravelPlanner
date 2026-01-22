import { Note } from "@/types/note";
import { Check, Pencil, Trash2, X } from "lucide-react";

interface NoteCardProps {
  note?: Note;
  isEditing: boolean;
  title: string;
  content: string;
  onTitleChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  titleInputRef?: React.RefObject<HTMLInputElement | null>;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

export default function NoteCard({
  note,
  isEditing,
  title,
  content,
  onTitleChange,
  onContentChange,
  onConfirm,
  onCancel,
  onEdit,
  onDelete,
  titleInputRef,
  containerRef,
}: NoteCardProps) {
  if (isEditing) {
    return (
      <div
        ref={containerRef}
        className="p-3 bg-gray-100 rounded-lg flex flex-col gap-2 border-2 border-blue-400 border-dashed"
      >
        <input
          ref={titleInputRef}
          type="text"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Enter note title..."
          className="font-semibold text-base bg-transparent border-none outline-none placeholder:text-gray-400"
        />

        <textarea
          value={content}
          onChange={(e) => {
            onContentChange(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = e.target.scrollHeight + "px";
          }}
          placeholder="Enter note content..."
          rows={2}
          className="text-sm text-gray-600 resize-none overflow-hidden bg-transparent border-none outline-none placeholder:text-gray-400"
        />

        <div className="flex justify-end gap-1 pt-1">
          <button
            onClick={onCancel}
            className="cursor-pointer p-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
            title="Cancel"
          >
            <X size={14} />
          </button>
          <button
            onClick={onConfirm}
            className="cursor-pointer p-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
            title="Confirm"
          >
            <Check size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group p-3 bg-gray-100 rounded-lg flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-base">{note?.title}</h3>

        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            className="cursor-pointer rounded-md p-2 bg-yellow-400 hover:bg-yellow-500 text-white"
            onClick={onEdit}
            title="Edit"
          >
            <Pencil size={14} />
          </button>
          <button
            className="cursor-pointer rounded-md p-2 bg-red-400 hover:bg-red-500 text-white"
            onClick={onDelete}
            title="Delete"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      <textarea
        value={note?.content}
        readOnly
        ref={(el) => {
          if (!el) return;
          el.style.height = "auto";
          el.style.height = el.scrollHeight + "px";
        }}
        className="text-sm text-gray-600 resize-none overflow-hidden bg-transparent focus:outline-none"
      />
    </div>
  );
}
