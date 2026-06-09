import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/__legacy__/ui/table";

import { PaginationControls } from "../../../../../components/__legacy__/ui/pagination-controls";
import { getAllUsers } from "../actions";
import { AdminAddMoneyButton } from "../../spending/components/AddMoneyButton";

export async function UserListTable({
  page = 1,
  search,
}: {
  page?: number;
  search?: string;
}) {
  const { users, pagination } = await getAllUsers(page, 20, search);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "—";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(dateStr));
  };

  return (
    <div className="space-y-4">
      <div className="rounded-md border bg-white">
        <Table>
          <TableHeader className="bg-gray-50">
            <TableRow>
              <TableHead className="font-medium">User</TableHead>
              <TableHead className="font-medium">Email</TableHead>
              <TableHead className="font-medium">Credit Balance</TableHead>
              <TableHead className="font-medium">Total Consumption</TableHead>
              <TableHead className="font-medium">Registered</TableHead>
              <TableHead className="text-right font-medium">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="py-10 text-center text-gray-500"
                >
                  No users found
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow
                  key={user.user_id}
                  className="hover:bg-gray-50 transition-colors"
                >
                  <TableCell className="font-medium">
                    {user.name || "—"}
                  </TableCell>
                  <TableCell className="text-gray-600">{user.email}</TableCell>
                  <TableCell>
                    <span className="font-medium text-green-600">
                      ${(user.balance / 100).toFixed(2)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-medium text-red-600">
                      ${(user.total_consumption / 100).toFixed(2)}
                    </span>
                  </TableCell>
                  <TableCell className="text-gray-500 text-sm">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <AdminAddMoneyButton
                      userId={user.user_id}
                      userEmail={user.email}
                      currentBalance={user.balance}
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <PaginationControls
        currentPage={page}
        totalPages={pagination.total_pages}
      />
    </div>
  );
}
