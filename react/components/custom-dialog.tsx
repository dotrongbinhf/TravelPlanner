import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface CustomDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  cancelLabel?: string;
  confirmLabel?: string;
  onCancel?: () => void;
  onConfirm?: () => void;
  cancelClassName?: string;
  confirmClassName?: string;
  confirmVariant?: "default" | "destructive";
  isDisabled?: boolean;
}

export function CustomDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  cancelLabel = "Cancel",
  confirmLabel = "Confirm",
  onCancel,
  onConfirm,
  cancelClassName,
  confirmClassName,
  confirmVariant = "default",
  isDisabled = false,
}: CustomDialogProps) {
  const handleCancel = () => {
    onCancel?.();
    onOpenChange(false);
  };

  const handleConfirm = () => {
    onConfirm?.();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] [&>button]:hidden">
        <DialogHeader className="relative">
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
          <DialogClose asChild>
            <button
              className="absolute -top-2 -right-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors duration-200 cursor-pointer"
              aria-label="Close"
            >
              <X className="w-5 h-5 text-gray-500 hover:text-gray-700" />
            </button>
          </DialogClose>
        </DialogHeader>
        {children}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCancel}
            className={cn(
              "bg-gray-50 hover:bg-gray-200",
              cancelClassName ?? "",
            )}
          >
            {cancelLabel}
          </Button>
          <Button
            onClick={handleConfirm}
            className={cn(
              "bg-blue-600 hover:bg-blue-700 text-white",
              confirmClassName ?? "",
            )}
            disabled={isDisabled}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
