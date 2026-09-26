import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import PageMeta from "@/components/common/PageMeta";
import Badge from "@/components/ui/badge/Badge";
import Button from "@/components/ui/button/Button";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { createUser, deleteUser, listUsers, updateUser, type UserUpdate } from "@/api/users";

export default function UserList() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ username: "", email: "", password: "" });
  const [form, setForm] = useState({
    username: "",
    email: "",
    role: "viewer",
    password: "",
  });

  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: UserUpdate }) =>
      updateUser(userId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setEditingId(null);
      setForm({ username: "", email: "", role: "viewer", password: "" });
    },
  });
  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setCreateForm({ username: "", email: "", password: "" });
      setIsCreateOpen(false);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const users = usersQuery.data ?? [];

  return (
    <>
      <PageMeta title="Users | IaC DriftWatch" description="Platform users" />
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Users</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Platform user list for admin review.
            </p>
          </div>
          <Button onClick={() => setIsCreateOpen((open) => !open)}>
            {isCreateOpen ? "Close" : "New User"}
          </Button>
        </div>

        {isCreateOpen && (
          <form
            className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3"
            onSubmit={(event) => {
              event.preventDefault();
              createMutation.mutate(createForm);
            }}
          >
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">New User</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <input className="h-11 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white" placeholder="Username" required value={createForm.username} onChange={(event) => setCreateForm({ ...createForm, username: event.target.value })} />
              <input type="email" className="h-11 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white" placeholder="Email" required value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} />
              <input type="password" className="h-11 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white" placeholder="Password" required value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} />
            </div>
            {createMutation.isError && <p className="text-sm text-error-500">Unable to create user.</p>}
            <div><Button disabled={createMutation.isPending}>{createMutation.isPending ? "Creating..." : "Create User"}</Button></div>
          </form>
        )}

        {usersQuery.isLoading && <p className="text-sm text-gray-500">Loading users...</p>}
        {usersQuery.error && (
          <p className="rounded-lg bg-error-50 p-4 text-sm text-error-700 dark:bg-error-500/10 dark:text-error-400">
            Unable to load users.
          </p>
        )}
        {!usersQuery.isLoading && !usersQuery.error && users.length === 0 && (
          <p className="rounded-lg border border-gray-200 p-6 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
            No users found.
          </p>
        )}

        {users.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
            <div className="max-w-full overflow-x-auto">
              <Table>
                <TableHeader className="border-b border-gray-100 dark:border-white/5">
                  <TableRow>
                    {['Username', 'Email', 'Role', 'Actions'].map((heading) => (
                      <TableCell key={heading} isHeader className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                        {heading}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                  {users.map((user) => (
                    <TableRow key={user.id}>
                      {editingId === user.id ? (
                        <>
                          <TableCell className="px-5 py-4 text-sm font-medium text-gray-800 dark:text-white/90">
                            <input
                              className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700 dark:text-white"
                              value={form.username}
                              onChange={(event) => setForm({ ...form, username: event.target.value })}
                              placeholder="Username"
                            />
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                            <input
                              className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700 dark:text-white"
                              value={form.email}
                              onChange={(event) => setForm({ ...form, email: event.target.value })}
                              placeholder="Email"
                            />
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm">
                            <select
                              className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700 dark:text-white"
                              value={form.role}
                              onChange={(event) => setForm({ ...form, role: event.target.value })}
                            >
                              <option value="admin">admin</option>
                              <option value="operator">operator</option>
                              <option value="viewer">viewer</option>
                              <option value="service">service</option>
                            </select>
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm">
                            <div className="flex flex-col gap-2">
                              <input
                                type="password"
                                className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700 dark:text-white"
                                value={form.password}
                                onChange={(event) => setForm({ ...form, password: event.target.value })}
                                placeholder="New password (optional)"
                              />
                              {updateMutation.isError && (
                                <p className="text-xs text-error-600 dark:text-error-400">
                                  Unable to update user.
                                </p>
                              )}
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => {
                                    const payload: UserUpdate = {
                                      username: form.username,
                                      email: form.email,
                                      role: form.role,
                                      ...(form.password.trim() ? { password: form.password } : {}),
                                    };
                                    updateMutation.mutate({ userId: user.id, payload });
                                  }}
                                  disabled={updateMutation.isPending}
                                >
                                  {updateMutation.isPending ? "Saving..." : "Save"}
                                </Button>
                                <Button variant="outline" onClick={() => setEditingId(null)} disabled={updateMutation.isPending}>
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          </TableCell>
                        </>
                      ) : (
                        <>
                          <TableCell className="px-5 py-4 text-sm font-medium text-gray-800 dark:text-white/90">
                            {user.username}
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                            {user.email}
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm">
                            <Badge
                              color={
                                user.role === "admin"
                                  ? "error"
                                  : user.role === "operator"
                                    ? "warning"
                                    : user.role === "viewer"
                                      ? "info"
                                      : "success"
                              }
                            >
                              {user.role}
                            </Badge>
                          </TableCell>
                          <TableCell className="px-5 py-4 text-sm">
                            <Button
                              variant="outline"
                              onClick={() => {
                                setEditingId(user.id);
                                setForm({
                                  username: user.username,
                                  email: user.email,
                                  role: user.role,
                                  password: "",
                                });
                              }}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="outline"
                              onClick={() => {
                                if (window.confirm(`Delete user ${user.username}?`)) {
                                  deleteMutation.mutate(user.id);
                                }
                              }}
                              disabled={deleteMutation.isPending}
                            >
                              Delete
                            </Button>
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
