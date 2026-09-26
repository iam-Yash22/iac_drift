import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router";
import ProtectedRoute from "./auth/ProtectedRoute";
import { ScrollToTop } from "./components/common/ScrollToTop";
import AppLayout from "./layout/AppLayout";
import SignIn from "./pages/AuthPages/SignIn";
import AccountDetail from "./pages/Accounts/AccountDetail";
import AccountList from "./pages/Accounts/AccountList";
import UserProfiles from "./pages/UserProfiles";
import SupportPage from "./pages/SupportPage";
import UserList from "./pages/Users/UserList";
import NotFound from "./pages/OtherPage/NotFound";

export default function App() {
  return (
    <>
      <Router>
        <ScrollToTop />
        <Routes>
          {/* Dashboard Layout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route index path="/" element={<Navigate to="/accounts" replace />} />
              <Route path="/profile" element={<UserProfiles />} />
              <Route path="/support" element={<SupportPage />} />
              <Route path="/accounts" element={<AccountList />} />
              <Route path="/accounts/:id" element={<AccountDetail />} />
              <Route element={<ProtectedRoute requiredRole="admin" />}>
                <Route path="/users" element={<UserList />} />
              </Route>
            </Route>
          </Route>

          {/* Auth Layout */}
          <Route path="/signin" element={<SignIn />} />

          {/* Fallback Route */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Router>
    </>
  );
}
