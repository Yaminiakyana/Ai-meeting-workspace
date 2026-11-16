import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "./store/authStore";

import LandingPage from "./pages/LandingPage";
import WorkspaceDashboard from "./pages/WorkspaceDashboard";
import Login from "./pages/Login";
import Meetings from "./pages/Meetings";
import MeetingDetails from "./pages/MeetingDetails";
import ActionItemsPage from "./pages/ActionItems";
import LiveMeetingRoom from "./pages/LiveMeetingRoom";

function isTokenExpired(token: string): boolean {
  try {
    const base64Url = token.split(".")[1];
    if (!base64Url) return true;
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const { exp } = JSON.parse(jsonPayload);
    if (!exp) return false;
    return Date.now() >= exp * 1000;
  } catch {
    return true;
  }
}

function RootRoute() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const isValid = accessToken && !isTokenExpired(accessToken);
  return isValid ? <WorkspaceDashboard /> : <LandingPage />;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  const location = useLocation();

  if (!accessToken || isTokenExpired(accessToken)) {
    if (accessToken) {
      useAuthStore.getState().logout();
    }
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRoute />} />
        <Route path="/login" element={<Login />} />

        {/* Protected workspace routes */}
        <Route
          path="/meetings"
          element={
            <ProtectedRoute>
              <Meetings />
            </ProtectedRoute>
          }
        />
        <Route
          path="/meetings/:meetingId"
          element={
            <ProtectedRoute>
              <MeetingDetails />
            </ProtectedRoute>
          }
        />
        <Route
          path="/meetings/:meetingId/room"
          element={
            <ProtectedRoute>
              <LiveMeetingRoom />
            </ProtectedRoute>
          }
        />
        <Route
          path="/room/:meetingId"
          element={
            <ProtectedRoute>
              <LiveMeetingRoom />
            </ProtectedRoute>
          }
        />
        <Route
          path="/action-items"
          element={
            <ProtectedRoute>
              <ActionItemsPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
