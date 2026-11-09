import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/authStore";

import LandingPage from "./pages/LandingPage";
import WorkspaceDashboard from "./pages/WorkspaceDashboard";
import Login from "./pages/Login";
import Meetings from "./pages/Meetings";
import MeetingDetails from "./pages/MeetingDetails";
import ActionItemsPage from "./pages/ActionItems";
import LiveMeetingRoom from "./pages/LiveMeetingRoom";

function RootRoute() {
  const accessToken = useAuthStore((state) => state.accessToken);
  return accessToken ? <WorkspaceDashboard /> : <LandingPage />;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const accessToken = useAuthStore((state) => state.accessToken);
  if (!accessToken) {
    return <Navigate to="/login" replace />;
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
