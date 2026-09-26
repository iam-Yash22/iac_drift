import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute({
  requiredRole,
}: {
  requiredRole?: "admin";
}) {
  const { user, role, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center text-gray-500">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/signin" replace state={{ from: location }} />;
  }

  if (requiredRole && role !== requiredRole) {
    return <Navigate to="/accounts" replace />;
  }

  return <Outlet />;
}
