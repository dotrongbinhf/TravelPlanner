"use client";

import {
  forwardRef,
  useState,
  useRef,
  useEffect,
  Dispatch,
  SetStateAction,
} from "react";
import {
  Calendar,
  Users,
  Wallet,
  MapPin,
  Camera,
  X,
  Check,
  Loader2,
  Pencil,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";
import { AxiosError } from "axios";
import { updatePlanBasicInfo, updatePlanCoverImage } from "@/api/plan/plan";
import { Plan } from "@/types/plan";
import { getLocaleFromCurrencyCode } from "@/utils/curency";
import {
  AdvancedImage,
  responsive,
  placeholder,
  lazyload,
} from "@cloudinary/react";
import { Cloudinary } from "@cloudinary/url-gen";
import { getResizedImageUrl } from "@/utils/image";

interface OverviewProps {
  planId: string;
  name: string;
  coverImageUrl?: string;
  startTime: Date;
  endTime: Date;
  budget: number;
  currencyCode: string;
  updatePlanName: (name: string) => void;
  updatePlanCoverImageUrl: (coverImageUrl: string) => void;
}

const Overview = forwardRef<HTMLDivElement, OverviewProps>(
  (
    {
      planId,
      name,
      coverImageUrl,
      startTime,
      endTime,
      budget,
      currencyCode,
      updatePlanName,
      updatePlanCoverImageUrl,
    },
    ref,
  ) => {
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Editing states
    const [isEditingName, setIsEditingName] = useState(false);
    const [editedName, setEditedName] = useState(name);
    const nameInputRef = useRef<HTMLInputElement>(null);
    const nameContainerRef = useRef<HTMLDivElement>(null);

    const cld = new Cloudinary({
      cloud: {
        cloudName: "dejauxt7c",
      },
    });

    const cIdImg = cld.image(`Plans_Cover/${planId}`);

    useEffect(() => {
      if (isEditingName && nameInputRef.current) {
        const timer = setTimeout(() => {
          if (nameInputRef.current) {
            nameInputRef.current.focus();
            const length = nameInputRef.current.value.length;
            nameInputRef.current.setSelectionRange(length, length);
          }
        }, 0);
        return () => clearTimeout(timer);
      }
    }, [isEditingName]);

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (
          isEditingName &&
          nameContainerRef.current &&
          !nameContainerRef.current.contains(event.target as Node)
        ) {
          handleCancelEditName();
        }
      };

      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }, [isEditingName]);

    const formatDate = (date: Date | null) => {
      if (!date || isNaN(date.getTime())) return "";
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    };

    const calculateDays = (start: Date | null, end: Date | null) => {
      if (!start || !end) return 0;
      const diffTime = end.getTime() - start.getTime();
      if (diffTime < 0) return 0;
      return Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1;
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        if (!file.type.startsWith("image/")) {
          toast.error("Please select an image file");
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          toast.error("Image size should be less than 5MB");
          return;
        }
        setSelectedFile(file);
        const objectUrl = URL.createObjectURL(file);
        setPreviewUrl(objectUrl);
      }
    };

    const handleCancelUploadCover = () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setSelectedFile(null);
      setPreviewUrl(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    };

    const handleConfirmUploadCover = async () => {
      if (!selectedFile) return;

      setIsUploading(true);
      try {
        const response = await updatePlanCoverImage(planId, selectedFile);
        updatePlanCoverImageUrl(response.coverImageUrl);

        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(null);
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }

        toast.success("Updated Cover Image");
      } catch (error) {
        console.error("Update Cover Image Failed:", error);
        if (error instanceof AxiosError) {
          toast.error(error.response?.data?.message ?? "Update Failed");
        } else {
          toast.error("Unexpected Error");
        }
      } finally {
        setIsUploading(false);
      }
    };

    const handleEditClick = () => {
      fileInputRef.current?.click();
    };

    const handleEditName = () => {
      setIsEditingName(true);
      setEditedName(name);
    };

    const handleConfirmEditName = async () => {
      if (editedName.trim()) {
        try {
          const response = await updatePlanBasicInfo(planId, {
            name: editedName.trim(),
          });
          updatePlanName(editedName.trim());
          toast.success("Updated Plan Name");
        } catch (error) {
          console.error("Update failed:", error);
          if (error instanceof AxiosError) {
            toast.error(error.response?.data ?? "Unexpected Error");
          } else {
            toast.error("Unexpected Update Error");
          }
        } finally {
          setIsEditingName(false);
        }
      } else {
        toast.error("Plan name cannot be empty");
      }
    };

    const handleCancelEditName = () => {
      setIsEditingName(false);
      setEditedName(name);
    };

    useEffect(() => {
      return () => {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
      };
    }, [previewUrl]);

    return (
      <div ref={ref} className="flex flex-col gap-4">
        {/* Cover Image */}
        <button
          className={cn(
            "relative w-full h-64 md:h-80 rounded-lg overflow-hidden bg-gray-200 group",
            !coverImageUrl && !previewUrl && "cursor-pointer",
          )}
          onClick={!coverImageUrl && !previewUrl ? handleEditClick : undefined}
        >
          {previewUrl ? (
            <img
              src={previewUrl}
              alt="Preview cover"
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : coverImageUrl ? (
            <img
              src={getResizedImageUrl(coverImageUrl, 1024)}
              alt="Current Cover"
              className="absolute inset-0 w-full h-full object-cover"
            />
          ) : (
            // <AdvancedImage
            //   cldImg={cIdImg}
            //   plugins={[
            //     responsive({
            //       steps: [200, 400, 600, 800, 1000, 1200, 1400, 1600],
            //     }),
            //     lazyload(),
            //     placeholder(),
            //   ]}
            //   className="absolute inset-0 w-full h-full object-cover"
            // />
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 bg-gradient-to-br from-gray-200 to-gray-300">
              <Camera size={56} className="text-gray-500" />
              <p className="mt-3 text-sm font-medium">No cover image</p>
              <p className="text-xs text-gray-500">Click to add an image</p>
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-purple-500 -z-10" />

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            className="hidden"
          />

          {!previewUrl && coverImageUrl && (
            <Button
              onClick={handleEditClick}
              variant="secondary"
              size="sm"
              className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
            >
              <Camera size={16} className="mr-1" />
              Edit Cover
            </Button>
          )}

          {previewUrl && (
            <div
              className={cn(
                "absolute bottom-3 right-3 flex items-center gap-2 bg-white/90 backdrop-blur-sm rounded-lg p-2 shadow-lg border border-gray-200",
                !isUploading && "animate-pulse hover:animate-none",
              )}
            >
              <Button
                onClick={handleCancelUploadCover}
                variant="ghost"
                size="icon"
                disabled={isUploading}
                className="h-8 w-8 bg-gray-300 hover:bg-gray-400 text-gray-700 disabled:opacity-50"
              >
                <X size={16} />
              </Button>
              <Button
                onClick={handleConfirmUploadCover}
                variant="ghost"
                size="icon"
                disabled={isUploading}
                className="h-8 w-8 bg-green-400 hover:bg-green-500 text-white hover:text-white disabled:opacity-50"
              >
                {isUploading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Check size={16} />
                )}
              </Button>
            </div>
          )}
        </button>

        {/* Plan Name */}
        {isEditingName ? (
          <div
            ref={nameContainerRef}
            className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 p-3 bg-gray-100 rounded-lg border-2 border-blue-400 border-dashed"
          >
            <input
              ref={nameInputRef}
              type="text"
              value={editedName}
              onChange={(e) => setEditedName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleConfirmEditName();
                }
              }}
              className="flex-1 min-w-0 text-2xl md:text-3xl font-bold text-gray-900 bg-transparent border-none outline-none"
              placeholder="Plan name..."
            />
            <div className="flex gap-1 flex-shrink-0 justify-end">
              <button
                onClick={handleCancelEditName}
                className="cursor-pointer p-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                title="Cancel"
              >
                <X size={16} />
              </button>
              <button
                onClick={handleConfirmEditName}
                className="cursor-pointer p-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
                title="Confirm"
              >
                <Check size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="group flex justify-between items-center gap-2">
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900">
              {name}
            </h1>
            <button
              onClick={handleEditName}
              className="cursor-pointer p-2 rounded-md bg-yellow-400 hover:bg-yellow-500 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              title="Edit"
            >
              <Pencil size={16} />
            </button>
          </div>
        )}

        {/* Overview Stats */}
        <div className="flex flex-wrap items-center justify-between gap-y-3 text-gray-700">
          {/* Date */}
          <div className="flex items-center gap-2">
            <Calendar size={20} className="text-blue-600 flex-shrink-0" />
            <span className="text-sm">
              {formatDate(startTime)} - {formatDate(endTime)}
              {/* <span className="text-gray-500 ml-1">
                ({calculateDays(startTime, endTime)} days)
              </span> */}
            </span>
          </div>

          {/* Members */}
          <div className="flex items-center gap-2">
            <Users size={20} className="text-green-600 flex-shrink-0" />
            <span className="text-sm">
              <span className="font-semibold">1</span> participant
            </span>
          </div>

          {/* Budget */}
          <div className="flex items-center gap-2">
            <Wallet size={20} className="text-amber-600 flex-shrink-0" />
            <span className="text-sm">
              <span className="font-semibold">
                {budget.toLocaleString(getLocaleFromCurrencyCode(currencyCode))}
              </span>{" "}
              {currencyCode}
            </span>
          </div>

          {/* Places */}
          <div className="flex items-center gap-2">
            <MapPin size={20} className="text-red-600 flex-shrink-0" />
            <span className="text-sm">
              <span className="font-semibold">15</span> places
            </span>
          </div>
        </div>
      </div>
    );
  },
);

Overview.displayName = "Overview";

export default Overview;
