import { CheckIcon } from "@/components/ui/check";
import { PackingList } from "@/types/packingList";
import { PackingItem } from "@/types/packingItem";
import {
  Check,
  Circle,
  CircleCheck,
  Plus,
  Pencil,
  Square,
  SquareCheck,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface PackingListCardProps {
  list?: PackingList;
  isEditing: boolean;
  name: string;
  onNameChange: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onToggleItem?: (itemId: string) => void;
  onAddItem?: (itemName: string) => Promise<void>;
  onEditItem?: (itemId: string, newName: string) => void;
  onDeleteItem?: (item: PackingItem) => void;
  nameInputRef?: React.RefObject<HTMLInputElement | null>;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

export default function PackingListCard({
  list,
  isEditing,
  name,
  onNameChange,
  onConfirm,
  onCancel,
  onEdit,
  onDelete,
  onToggleItem,
  onAddItem,
  onEditItem,
  onDeleteItem,
  nameInputRef,
  containerRef,
}: PackingListCardProps) {
  const [isAddingItem, setIsAddingItem] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const newItemInputRef = useRef<HTMLInputElement>(null);
  const newItemContainerRef = useRef<HTMLDivElement>(null);

  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editItemName, setEditItemName] = useState("");
  const editItemInputRef = useRef<HTMLInputElement>(null);
  const editItemContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isAddingItem && newItemInputRef.current) {
      newItemInputRef.current.focus();
    }
  }, [isAddingItem]);

  useEffect(() => {
    if (editingItemId && editItemInputRef.current) {
      editItemInputRef.current.focus();
    }
  }, [editingItemId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isAddingItem &&
        newItemContainerRef.current &&
        !newItemContainerRef.current.contains(event.target as Node)
      ) {
        setIsAddingItem(false);
        setNewItemName("");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isAddingItem]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        editingItemId &&
        editItemContainerRef.current &&
        !editItemContainerRef.current.contains(event.target as Node)
      ) {
        setEditingItemId(null);
        setEditItemName("");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [editingItemId]);

  const handleConfirmAddItem = async () => {
    if (newItemName.trim() && onAddItem) {
      await onAddItem(newItemName.trim());
    }
    setIsAddingItem(false);
    setNewItemName("");
  };

  const handleCancelAddItem = () => {
    setIsAddingItem(false);
    setNewItemName("");
  };

  const handleStartEditItem = (itemId: string, itemName: string) => {
    setEditingItemId(itemId);
    setEditItemName(itemName);
  };

  const handleConfirmEditItem = () => {
    if (editingItemId && editItemName.trim() && onEditItem) {
      onEditItem(editingItemId, editItemName.trim());
    }
    setEditingItemId(null);
    setEditItemName("");
  };

  const handleCancelEditItem = () => {
    setEditingItemId(null);
    setEditItemName("");
  };

  const isListEditing = isEditing;
  const isItemsDisabled = isListEditing;

  return (
    <div className="flex flex-col gap-3">
      {/* List Header */}
      {isEditing ? (
        <div
          ref={containerRef}
          className="flex items-center gap-2 border-2 rounded-lg border-blue-400 border-dashed p-1"
        >
          <input
            ref={nameInputRef}
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Enter list name..."
            className="flex-1 font-semibold text-base bg-transparent border-none outline-none placeholder:text-gray-400"
          />

          <div className="flex gap-1">
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
      ) : (
        <div className="group flex justify-between items-center">
          <h3 className="font-semibold text-base">{list?.name}</h3>

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
      )}

      {/* Items */}
      <div
        className={`flex flex-col gap-3 ${isItemsDisabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        {list?.packingItems?.map((item) => (
          <div key={item.id}>
            {editingItemId === item.id ? (
              <div
                ref={editItemContainerRef}
                className="font-medium p-3 bg-gray-100 rounded-lg flex items-center gap-2 border-2 border-blue-400 border-dashed"
              >
                {item.isPacked ? (
                  <Check
                    className="text-white bg-[#2B7FFF] rounded-full p-1"
                    size={18}
                    strokeWidth={3}
                  />
                ) : (
                  <Circle size={18} className="text-gray-400" />
                )}
                <input
                  ref={editItemInputRef}
                  type="text"
                  value={editItemName}
                  onChange={(e) => setEditItemName(e.target.value)}
                  placeholder="Enter item name..."
                  className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-gray-400"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleConfirmEditItem();
                    if (e.key === "Escape") handleCancelEditItem();
                  }}
                />

                <div className="flex gap-1">
                  <button
                    onClick={handleCancelEditItem}
                    className="cursor-pointer p-1.5 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                    title="Cancel"
                  >
                    <X size={14} />
                  </button>
                  <button
                    onClick={handleConfirmEditItem}
                    className="cursor-pointer p-1.5 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
                    title="Confirm"
                  >
                    <Check size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div
                className={`font-medium group/item p-3 bg-gray-100 rounded-lg flex items-center justify-between ${isItemsDisabled ? "pointer-events-none" : ""}`}
              >
                <div
                  className="flex items-center gap-2 cursor-pointer flex-1"
                  onClick={() => onToggleItem?.(item.id)}
                >
                  {item.isPacked ? (
                    <CheckIcon
                      className="text-white bg-[#2B7FFF] rounded-full p-1"
                      size={10}
                      animateOnMount={true}
                      disableHover={true}
                    />
                  ) : (
                    <Circle size={18} className="text-gray-400" />
                  )}
                  <span className={`text-sm text-gray-700`}>{item.name}</span>
                </div>

                <div className="flex gap-1 opacity-0 group-hover/item:opacity-100 transition-opacity">
                  <button
                    className="cursor-pointer rounded-md p-1.5 bg-yellow-400 hover:bg-yellow-500 text-white"
                    onClick={() => handleStartEditItem(item.id, item.name)}
                    title="Edit item"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    className="cursor-pointer rounded-md p-1.5 bg-red-400 hover:bg-red-500 text-white"
                    onClick={() => onDeleteItem?.(item)}
                    title="Delete item"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Add Item Form */}
        {isAddingItem ? (
          <div
            ref={newItemContainerRef}
            className={`font-medium p-3 bg-gray-100 rounded-lg flex items-center gap-2 border-2 border-blue-400 border-dashed ${isItemsDisabled ? "pointer-events-none" : ""}`}
          >
            <Circle size={18} className="text-gray-400" />
            <input
              ref={newItemInputRef}
              type="text"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              placeholder="Enter item name..."
              className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-gray-400"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleConfirmAddItem();
                if (e.key === "Escape") handleCancelAddItem();
              }}
            />

            <div className="flex gap-1">
              <button
                onClick={handleCancelAddItem}
                className="cursor-pointer p-1.5 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                title="Cancel"
              >
                <X size={14} />
              </button>
              <button
                onClick={handleConfirmAddItem}
                className="cursor-pointer p-1.5 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
                title="Confirm"
              >
                <Check size={14} />
              </button>
            </div>
          </div>
        ) : (
          <button
            className={`cursor-pointer px-4 py-3 flex gap-2 items-center justify-center rounded-lg border border-2 border-dashed border-gray-300 text-gray-500 hover:border-green-400 hover:text-green-500 hover:bg-green-50 transition-all duration-200 ${isItemsDisabled ? "pointer-events-none" : ""}`}
            onClick={() => setIsAddingItem(true)}
            disabled={isItemsDisabled}
          >
            <Plus size={16} strokeWidth={3} />
            <span className="text-sm font-medium">Add an item</span>
          </button>
        )}
      </div>
    </div>
  );
}
