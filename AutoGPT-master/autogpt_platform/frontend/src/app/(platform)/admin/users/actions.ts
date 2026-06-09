"use server";

import { revalidatePath } from "next/cache";
import BackendApi from "@/lib/autogpt-server-api";
import type { AdminUsersListResponse } from "@/lib/autogpt-server-api/types";

export async function addDollarsToUser(formData: FormData) {
  const data = {
    user_id: formData.get("id") as string,
    amount: parseInt(formData.get("amount") as string),
    comments: formData.get("comments") as string,
  };
  const api = new BackendApi();
  await api.addUserCredits(data.user_id, data.amount, data.comments);
  revalidatePath("/admin/users");
}

export async function getAllUsers(
  page: number = 1,
  pageSize: number = 20,
  search?: string,
): Promise<AdminUsersListResponse> {
  const api = new BackendApi();
  const result = await api.listAllUsers({
    page,
    page_size: pageSize,
    search,
  });
  return result;
}
