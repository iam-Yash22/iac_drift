import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import PageMeta from "@/components/common/PageMeta";
import Button from "@/components/ui/button/Button";
import Badge from "@/components/ui/badge/Badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/auth/AuthContext";
import { createAccount, deleteAccount, listAccounts } from "@/api/accounts";
import type { AccountCreate } from "@/api/accounts";

const emptyForm: AccountCreate = {
  name: "",
  account_id: "",
  role_arn: "",
  is_active: true,
};

export default function AccountList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const [form, setForm] = useState<AccountCreate>(emptyForm);
  const [isFormOpen, setIsFormOpen] = useState(false);

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: listAccounts,
  });
  const createMutation = useMutation({
    mutationFn: createAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setForm(emptyForm);
      setIsFormOpen(false);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["accounts"] }),
  });

  const accounts = accountsQuery.data ?? [];

  return (
    <>
      <PageMeta title="Accounts | IaC DriftWatch" description="Monitored AWS accounts" />
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Accounts</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Monitored AWS accounts and their latest scan state.
            </p>
          </div>
          {role === "admin" && (
            <Button onClick={() => setIsFormOpen((open) => !open)}>
              {isFormOpen ? "Close" : "New Account"}
            </Button>
          )}
        </div>

        {role === "admin" && isFormOpen && (
          <form
            className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/3"
            onSubmit={(event) => {
              event.preventDefault();
              createMutation.mutate(form);
            }}
          >
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">New Account</h2>
            <div className="grid gap-4 md:grid-cols-3">
              <input
                className="h-11 rounded-lg border border-gray-300 bg-transparent px-4 text-sm dark:border-gray-700 dark:text-white"
                placeholder="Account name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
              <input
                className="h-11 rounded-lg border border-gray-300 bg-transparent px-4 text-sm dark:border-gray-700 dark:text-white"
                placeholder="AWS account ID"
                value={form.account_id}
                onChange={(event) => setForm({ ...form, account_id: event.target.value })}
                required
              />
              <input
                className="h-11 rounded-lg border border-gray-300 bg-transparent px-4 text-sm dark:border-gray-700 dark:text-white"
                placeholder="IAM role ARN"
                value={form.role_arn}
                onChange={(event) => setForm({ ...form, role_arn: event.target.value })}
                required
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Active
            </label>
            {createMutation.error && (
              <p className="text-sm text-error-500">Unable to create account.</p>
            )}
            <div>
              <Button disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Account"}
              </Button>
            </div>
          </form>
        )}

        {accountsQuery.isLoading && <p className="text-sm text-gray-500">Loading accounts...</p>}
        {accountsQuery.error && (
          <p className="rounded-lg bg-error-50 p-4 text-sm text-error-700 dark:bg-error-500/10 dark:text-error-400">
            Unable to load accounts.
          </p>
        )}
        {!accountsQuery.isLoading && !accountsQuery.error && accounts.length === 0 && (
          <p className="rounded-lg border border-gray-200 p-6 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
            No accounts yet.
          </p>
        )}
        {accounts.length > 0 && (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
            <div className="max-w-full overflow-x-auto">
              <Table>
                <TableHeader className="border-b border-gray-100 dark:border-white/5">
                  <TableRow>
                    {['Name', 'Account ID', 'Status', 'Last scan', 'Actions'].map((heading) => (
                      <TableCell key={heading} isHeader className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                        {heading}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                  {accounts.map((account) => (
                    <TableRow
                      key={account.id}
                      className="cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5"
                      onClick={() => navigate(`/accounts/${account.id}`)}
                    >
                      <TableCell className="px-5 py-4 text-sm font-medium text-gray-800 dark:text-white/90">
                        {account.name}
                      </TableCell>
                      <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                        {account.account_id}
                      </TableCell>
                      <TableCell className="px-5 py-4 text-sm">
                        <Badge color={account.is_active ? "success" : "error"}>
                          {account.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">Unavailable</TableCell>
                      <TableCell className="px-5 py-4 text-sm">
                        {role === "admin" && (
                          <Button
                            variant="outline"
                            onClick={(event) => {
                              event.stopPropagation();
                              if (window.confirm(`Delete account ${account.name}?`)) {
                                deleteMutation.mutate(account.id);
                              }
                            }}
                            disabled={deleteMutation.isPending}
                          >
                            Delete
                          </Button>
                        )}
                      </TableCell>
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
