"use client";

import { forwardRef, useState } from "react";
import { Check, X, Eye, EyeOff, Loader2 } from "lucide-react";
import { changePassword } from "@/api/user/user";
import toast from "react-hot-toast";
import { AxiosError } from "axios";

const ChangePassword = forwardRef<HTMLDivElement>(
  function ChangePassword(_, ref) {
    const [currentPassword, setcurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [isUpdating, setIsUpdating] = useState(false);

    const [showcurrentPassword, setShowcurrentPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

    const hasChanges = currentPassword || newPassword || confirmPassword;
    const isFormValid =
      currentPassword &&
      newPassword &&
      confirmPassword &&
      newPassword === confirmPassword;

    const handleCancel = () => {
      setcurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowcurrentPassword(false);
      setShowNewPassword(false);
      setShowConfirmPassword(false);
    };

    const handleUpdate = async () => {
      if (newPassword !== confirmPassword) {
        toast.error("New passwords do not match");
        return;
      }

      setIsUpdating(true);
      try {
        await changePassword({
          currentPassword,
          newPassword,
        });
        toast.success("Changed Password");
        handleCancel();
      } catch (error) {
        console.error("Error changing password:", error);
        if (error instanceof AxiosError) {
          toast.error(error.response?.data ?? "Failed to change password");
        } else {
          toast.error("Failed to change password");
        }
      } finally {
        setIsUpdating(false);
      }
    };

    return (
      <section
        ref={ref}
        id="change-password"
        data-section-id="change-password"
        className="flex flex-col gap-4"
      >
        <h2 className="text-2xl font-bold text-gray-800">Change Password</h2>

        <div className="flex flex-col gap-4">
          {/* Current Password */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              Current Password
            </label>
            <div className="relative">
              <input
                type={showcurrentPassword ? "text" : "password"}
                value={currentPassword}
                onChange={(e) => setcurrentPassword(e.target.value)}
                placeholder="Enter current password..."
                autoComplete="new-password"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-400"
              />
              <button
                tabIndex={-1}
                type="button"
                onClick={() => setShowcurrentPassword(!showcurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showcurrentPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              New Password
            </label>
            <div className="relative">
              <input
                type={showNewPassword ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password..."
                autoComplete="new-password"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-400"
              />
              <button
                tabIndex={-1}
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showNewPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Confirm New Password */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              Confirm New Password
            </label>
            <div className="relative">
              <input
                type={showConfirmPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password..."
                autoComplete="new-password"
                className={`w-full px-3 py-2 pr-10 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  confirmPassword && newPassword !== confirmPassword
                    ? "border-red-400 focus:border-red-400"
                    : "border-gray-300 focus:border-blue-400"
                }`}
              />
              <button
                tabIndex={-1}
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
              >
                {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {confirmPassword && newPassword !== confirmPassword && (
              <span className="text-xs text-red-500">
                Passwords do not match
              </span>
            )}
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
              disabled={!isFormValid || isUpdating}
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

export default ChangePassword;
