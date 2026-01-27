"use client";

import { forwardRef, useState, useRef, useEffect } from "react";
import { User } from "@/types/user";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Camera, Check, X, Loader2, Pencil } from "lucide-react";
import { updateUserProfile, updateAvatar } from "@/api/user/user";
import toast from "react-hot-toast";
import { AxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getResizedImageUrl } from "@/utils/image";

interface UserInformationProps {
  user: User;
  updateUser: (user: User) => void;
}

const UserInformation = forwardRef<HTMLDivElement, UserInformationProps>(
  function UserInformation({ user, updateUser }, ref) {
    const [editName, setEditName] = useState(user.name);
    const [editEmail, setEditEmail] = useState(user.email);
    const [isUpdating, setIsUpdating] = useState(false);

    // Avatar upload states
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Reset form when user changes
    useEffect(() => {
      setEditName(user.name);
      setEditEmail(user.email);
    }, [user]);

    const hasChanges = editName !== user.name || editEmail !== user.email;

    const handleCancel = () => {
      setEditName(user.name);
      setEditEmail(user.email);
    };

    const handleUpdate = async () => {
      setIsUpdating(true);
      try {
        const updatedUser = await updateUserProfile({
          name: editName.trim(),
          email: editEmail.trim(),
        });
        updateUser(updatedUser);
        toast.success("Updated Profile");
      } catch (error) {
        console.error("Error updating profile:", error);
        if (error instanceof AxiosError) {
          toast.error(error.response?.data ?? "Failed to update profile");
        } else {
          toast.error("Failed to update profile");
        }
      } finally {
        setIsUpdating(false);
      }
    };

    // Avatar handling
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

    const handleCancelUpload = () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
      setSelectedFile(null);
      setPreviewUrl(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    };

    const handleConfirmUpload = async () => {
      if (!selectedFile) return;

      setIsUploading(true);
      try {
        const response = await updateAvatar(selectedFile);
        updateUser({ ...user, avatarUrl: response.avatarUrl });

        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(null);
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }

        toast.success("Updated Avatar");
      } catch (error) {
        console.error("Update Avatar Failed:", error);
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

    useEffect(() => {
      return () => {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
      };
    }, [previewUrl]);

    return (
      <section
        ref={ref}
        id="user-information"
        data-section-id="user-information"
        className="flex flex-col gap-4"
      >
        <h2 className="text-2xl font-bold text-gray-800">User Information</h2>

        <div className="flex flex-col gap-4">
          {/* Avatar - Centered and Large with External Icons */}
          <div className="flex justify-center">
            <div className="relative">
              {/* Avatar Circle */}
              <button
                className={cn(
                  "relative w-32 h-32 rounded-full overflow-hidden bg-gray-200 border-2 border-gray-200",
                  !user.avatarUrl && !previewUrl && "cursor-pointer",
                )}
                onClick={
                  !user.avatarUrl && !previewUrl ? handleEditClick : undefined
                }
              >
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Preview avatar"
                    className="w-full h-full object-cover"
                  />
                ) : user.avatarUrl ? (
                  <img
                    src={getResizedImageUrl(user.avatarUrl, 256, 256)}
                    alt="Current Avatar"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 bg-gradient-to-br from-gray-200 to-gray-300">
                    <Camera size={32} className="text-gray-500" />
                    <p className="mt-1 text-xs font-medium">Add photo</p>
                  </div>
                )}
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {/* Edit Button - Top Right Outside Avatar */}
              {!previewUrl && user.avatarUrl && (
                <Button
                  onClick={handleEditClick}
                  variant="secondary"
                  size="sm"
                  className="absolute -top-1 -right-[16px] shadow-lg h-8 w-8 p-0 rounded-full bg-yellow-400 hover:bg-yellow-500 text-white hover:text-white"
                >
                  <Pencil size={14} />
                </Button>
              )}

              {/* Confirm/Cancel Buttons - Bottom Right Outside Avatar */}
              {previewUrl && (
                <div className="absolute -bottom-1 -right-[34px] flex items-center gap-1">
                  <Button
                    onClick={handleCancelUpload}
                    variant="ghost"
                    size="icon"
                    disabled={isUploading}
                    className="shadow-lg h-8 w-8 p-0 rounded-full bg-gray-300 hover:bg-gray-400 hover:text-white disabled:opacity-50"
                  >
                    <X size={14} />
                  </Button>
                  <Button
                    onClick={handleConfirmUpload}
                    variant="ghost"
                    size="icon"
                    disabled={isUploading}
                    className="shadow-lg h-8 w-8 p-0 rounded-full bg-green-400 hover:bg-green-500 text-white hover:text-white disabled:opacity-50"
                  >
                    {isUploading ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Check size={14} />
                    )}
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Username (Read-only) */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              Username
            </label>
            <input
              type="text"
              value={user.username}
              disabled
              autoComplete="off"
              className="px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-500 cursor-not-allowed"
            />
          </div>

          {/* Name */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="Enter your name..."
              autoComplete="off"
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-400"
            />
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
              placeholder="Enter your email..."
              autoComplete="off" //to turn off auto complete
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-400"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={handleCancel}
              disabled={!hasChanges || isUpdating}
              className="cursor-pointer px-4 py-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <X size={16} />
              <span className="text-sm font-medium">Cancel</span>
            </button>
            <button
              onClick={handleUpdate}
              disabled={!hasChanges || isUpdating}
              className="cursor-pointer px-4 py-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUpdating ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Check size={16} />
              )}
              <span className="text-sm font-medium">Update</span>
            </button>
          </div>
        </div>
      </section>
    );
  },
);

export default UserInformation;
