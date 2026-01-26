import { useState } from "react";
import { Search, UserPlus } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { CustomDialog } from "@/components/custom-dialog";
import { Badge } from "@/components/ui/badge";
import { findUserByNameOrUsername } from "@/api/user/user";
import toast from "react-hot-toast";
import { getResizedImageUrl } from "@/utils/image";
import { User } from "@/types/user";
import { PlanRole } from "@/api/participant/types";

interface InviteTeammateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvite: (user: User, role: PlanRole) => void;
  existingTeammateIds: string[];
}

export default function InviteTeammateDialog({
  open,
  onOpenChange,
  onInvite,
  existingTeammateIds,
}: InviteTeammateDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<User[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<PlanRole>(PlanRole.Viewer);

  const getInitials = (name?: string, username?: string) => {
    const displayName = name?.trim() || username?.trim() || "";
    if (!displayName) return "U";

    const parts = displayName.split(/\s+/);
    if (parts.length === 1) {
      return parts[0].slice(0, 2).toUpperCase();
    }
    return (parts[0][0] + parts[1][0]).toUpperCase();
  };

  const handleSearch = async () => {
    setSelectedUser(null);
    setSelectedRole(PlanRole.Viewer);
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setHasSearched(false);
      return;
    }

    setIsSearching(true);

    try {
      const users = await findUserByNameOrUsername(searchQuery);
      // Filter out users who are already teammates
      const filteredUsers = users.filter(
        (user) => !existingTeammateIds.includes(user.id),
      );
      setSearchResults(filteredUsers);
      setHasSearched(true);
    } catch (error) {
      console.error("Failed to search users:", error);
      toast.error("Failed to search users");
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectUser = (user: User) => {
    setSelectedUser(user);
  };

  const handleInvite = async () => {
    if (!selectedUser) return;

    try {
      onInvite(selectedUser, selectedRole);
      handleReset();
      onOpenChange(false);
    } catch (error) {
      console.error("Failed to invite teammate:", error);
    }
  };

  const handleReset = () => {
    setSearchQuery("");
    setSearchResults([]);
    setHasSearched(false);
    setSelectedUser(null);
    setSelectedRole(PlanRole.Viewer);
    setIsSearching(false);
  };

  const handleCancel = () => {
    handleReset();
  };

  return (
    <CustomDialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) handleReset();
        onOpenChange(isOpen);
      }}
      title="Invite Teammate"
      description="Search for users to invite to your plan"
      cancelLabel="Cancel"
      confirmLabel={
        <>
          <UserPlus size={16} className="" />
          Send Invite
        </>
      }
      onCancel={handleCancel}
      onConfirm={handleInvite}
      confirmClassName="bg-green-500 hover:bg-green-600"
      isDisabled={!selectedUser}
    >
      <div className="flex flex-col gap-4 py-2">
        {/* Search Input */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
              size={16}
            />
            <Input
              placeholder="Search by name or username..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSearch();
              }}
              className="pl-9"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={isSearching}
            className="cursor-pointer px-4 py-2 flex items-center bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Search
          </button>
        </div>

        {/* Search Results */}
        {isSearching && (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
          </div>
        )}

        {!isSearching && hasSearched && (
          <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
            {searchResults.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4 bg-gray-50 rounded-lg">
                No users found matching your search.
              </p>
            ) : (
              searchResults.map((user) => (
                <div
                  key={user.id}
                  onClick={() => handleSelectUser(user)}
                  className={`p-3 rounded-lg flex items-center gap-3 cursor-pointer transition-colors ${
                    selectedUser?.id === user.id
                      ? "bg-blue-50 border-2 border-blue-400"
                      : "bg-gray-100 hover:bg-gray-200"
                  }`}
                >
                  <Avatar className="h-10 w-10">
                    <AvatarImage
                      src={getResizedImageUrl(user.avatarUrl ?? "", 256, 256)}
                      alt={user.name}
                    />
                    <AvatarFallback className="bg-blue-500 text-white text-sm">
                      {getInitials(user.name, user.username)}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-gray-700">
                      {user.username}
                    </span>
                    <span className="text-xs text-gray-500">{user.name}</span>
                  </div>

                  {selectedUser?.id === user.id && (
                    <Badge className="ml-auto bg-blue-100 text-blue-700 hover:bg-blue-100">
                      Selected
                    </Badge>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Selected User & Role Selection */}
        {/* {selectedUser && (
          <div className="flex flex-col gap-3 p-3 bg-gray-100 rounded-lg border-2 border-blue-400 border-dashed">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10">
                  <AvatarImage
                    src={getResizedImageUrl(
                      selectedUser.avatarUrl ?? "",
                      256,
                      256,
                    )}
                    alt={selectedUser.name}
                  />
                  <AvatarFallback className="bg-blue-500 text-white text-sm">
                    {getInitials(selectedUser.name, selectedUser.username)}
                  </AvatarFallback>
                </Avatar>

                <div className="flex flex-col">
                  <span className="text-sm font-medium text-gray-700">
                    {selectedUser.username}
                  </span>
                  <span className="text-xs text-gray-500">
                    {selectedUser.name}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setSelectedUser(null)}
                className="cursor-pointer p-1.5 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                title="Remove selection"
              >
                <span className="text-xs font-medium">×</span>
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600 font-medium">
                Assign Role:
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50 transition-colors flex items-center gap-2">
                    <Badge
                      variant="secondary"
                      className={getRoleBadgeColor(selectedRole)}
                    >
                      {
                        TEAMMATE_ROLES.find((r) => r.value === selectedRole)
                          ?.label
                      }
                    </Badge>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {TEAMMATE_ROLES.filter((r) => r.value !== PlanRole.Owner).map(
                    (role) => (
                      <DropdownMenuItem
                        key={role.value}
                        onClick={() => setSelectedRole(role.value)}
                        className="cursor-pointer"
                      >
                        <Badge
                          variant="secondary"
                          className={getRoleBadgeColor(role.value)}
                        >
                          {role.label}
                        </Badge>
                      </DropdownMenuItem>
                    ),
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        )} */}
      </div>
    </CustomDialog>
  );
}
