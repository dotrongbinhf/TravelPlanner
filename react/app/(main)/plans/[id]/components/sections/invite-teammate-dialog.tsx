import { useState } from "react";
import { User, TeammateRole, TEAMMATE_ROLES } from "@/types/teammate";
import { Search, UserPlus, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// Mock users for search
const MOCK_USERS: User[] = [
  { id: "u1", name: "Alice Johnson", email: "alice@example.com" },
  { id: "u2", name: "Bob Smith", email: "bob@example.com" },
  { id: "u3", name: "Charlie Brown", email: "charlie@example.com" },
  { id: "u4", name: "Diana Ross", email: "diana@example.com" },
  { id: "u5", name: "Edward Norton", email: "edward@example.com" },
  { id: "u6", name: "Fiona Apple", email: "fiona@example.com" },
];

interface InviteTeammateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvite: (user: User, role: TeammateRole) => void;
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
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [selectedRole, setSelectedRole] = useState<TeammateRole>("viewer");

  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const handleSearch = () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setHasSearched(false);
      return;
    }

    const query = searchQuery.toLowerCase();
    const results = MOCK_USERS.filter(
      (user) =>
        !existingTeammateIds.includes(user.id) &&
        (user.name.toLowerCase().includes(query) ||
          user.email.toLowerCase().includes(query)),
    );
    setSearchResults(results);
    setHasSearched(true);
  };

  const handleSelectUser = (user: User) => {
    setSelectedUser(user);
  };

  const handleInvite = () => {
    if (selectedUser) {
      onInvite(selectedUser, selectedRole);
      handleReset();
      onOpenChange(false);
    }
  };

  const handleReset = () => {
    setSearchQuery("");
    setSearchResults([]);
    setHasSearched(false);
    setSelectedUser(null);
    setSelectedRole("viewer");
  };

  const handleClose = () => {
    handleReset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Invite Teammate</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Search Input */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search
                className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                size={16}
              />
              <Input
                placeholder="Search by name or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
                className="pl-9"
              />
            </div>
            <Button onClick={handleSearch} variant="secondary">
              Search
            </Button>
          </div>

          {/* Search Results */}
          {hasSearched && (
            <div className="flex flex-col gap-2 max-h-48 overflow-y-auto">
              {searchResults.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">
                  No users found matching your search.
                </p>
              ) : (
                searchResults.map((user) => (
                  <div
                    key={user.id}
                    onClick={() => handleSelectUser(user)}
                    className={`p-2 rounded-lg flex items-center gap-3 cursor-pointer transition-colors ${
                      selectedUser?.id === user.id
                        ? "bg-blue-100 border-2 border-blue-400"
                        : "bg-gray-50 hover:bg-gray-100"
                    }`}
                  >
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={user.avatar} alt={user.name} />
                      <AvatarFallback className="bg-blue-500 text-white text-xs">
                        {getInitials(user.name)}
                      </AvatarFallback>
                    </Avatar>

                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-gray-700">
                        {user.name}
                      </span>
                      <span className="text-xs text-gray-500">
                        {user.email}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Selected User & Role Selection */}
          {selectedUser && (
            <div className="flex flex-col gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-10 w-10">
                    <AvatarImage
                      src={selectedUser.avatar}
                      alt={selectedUser.name}
                    />
                    <AvatarFallback className="bg-blue-500 text-white text-sm">
                      {getInitials(selectedUser.name)}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-gray-700">
                      {selectedUser.name}
                    </span>
                    <span className="text-xs text-gray-500">
                      {selectedUser.email}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => setSelectedUser(null)}
                  className="p-1 rounded-md hover:bg-gray-200 text-gray-500"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Role:</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50 transition-colors">
                      {
                        TEAMMATE_ROLES.find((r) => r.value === selectedRole)
                          ?.label
                      }
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {TEAMMATE_ROLES.filter((r) => r.value !== "owner").map(
                      (role) => (
                        <DropdownMenuItem
                          key={role.value}
                          onClick={() => setSelectedRole(role.value)}
                          className="cursor-pointer"
                        >
                          {role.label}
                        </DropdownMenuItem>
                      ),
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              onClick={handleInvite}
              disabled={!selectedUser}
              className="bg-green-500 hover:bg-green-600"
            >
              <UserPlus size={16} className="mr-2" />
              Send Invite
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
