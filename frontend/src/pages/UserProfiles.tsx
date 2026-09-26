import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import PageMeta from "@/components/common/PageMeta";
import { useAuth } from "@/auth/AuthContext";

export default function UserProfiles() {
  const { user, isLoading } = useAuth();

  return (
    <>
      <PageMeta title="Profile | IaC Driftwatch" description="Current user profile" />
      <PageBreadcrumb pageTitle="Profile" />
      <div className="rounded-2xl border border-gray-200 bg-white p-5 lg:p-6 dark:border-gray-800 dark:bg-white/3">
        <h3 className="mb-5 text-lg font-semibold text-gray-800 lg:mb-7 dark:text-white/90">
          Profile
        </h3>

        {isLoading && <p className="text-sm text-gray-500">Loading profile...</p>}
        {!isLoading && !user && (
          <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
            No current user profile is available.
          </p>
        )}

        {user && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <p className="text-xs uppercase tracking-wide text-gray-500">Username</p>
              <p className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">{user.username}</p>
            </div>
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <p className="text-xs uppercase tracking-wide text-gray-500">Email</p>
              <p className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">{user.email}</p>
            </div>
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800 md:col-span-2">
              <p className="text-xs uppercase tracking-wide text-gray-500">Role</p>
              <p className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">{user.role}</p>
            </div>
          </div>
        )}

        <p className="mt-6 text-sm text-gray-500 dark:text-gray-400">
          The current-user contract is /api/v1/auth/me; the backend exposes no /users/me self-update route, so this profile view is read-only.
        </p>
      </div>
    </>
  );
}
