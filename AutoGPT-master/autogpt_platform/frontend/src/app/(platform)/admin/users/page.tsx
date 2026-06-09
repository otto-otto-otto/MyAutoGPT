import { withRoleAccess } from "@/lib/withRoleAccess";
import { Suspense } from "react";
import { UserListTable } from "./components/UserListTable";
import { UserSearchBar } from "./components/UserSearchBar";

type UsersPageSearchParams = {
  page?: string;
  search?: string;
};

function AdminUsers({
  searchParams,
}: {
  searchParams: UsersPageSearchParams;
}) {
  const page = searchParams.page ? Number.parseInt(searchParams.page) : 1;
  const search = searchParams.search;

  return (
    <div className="mx-auto p-6">
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">User Management</h1>
            <p className="text-gray-500">
              View and manage all users and their credit information
            </p>
          </div>
        </div>

        <UserSearchBar initialSearch={search} />

        <Suspense
          key={`${page}-${search}`}
          fallback={
            <div className="py-10 text-center text-gray-500">
              Loading users...
            </div>
          }
        >
          <UserListTable page={page} search={search} />
        </Suspense>
      </div>
    </div>
  );
}

export default async function AdminUsersPage({
  searchParams,
}: {
  searchParams: Promise<UsersPageSearchParams>;
}) {
  "use server";
  const withAdminAccess = await withRoleAccess(["admin"]);
  const ProtectedAdminUsers = await withAdminAccess(AdminUsers);
  return <ProtectedAdminUsers searchParams={await searchParams} />;
}
