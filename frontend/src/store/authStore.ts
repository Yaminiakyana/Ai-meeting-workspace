import { create } from "zustand";
import { persist } from "zustand/middleware";
import axios from "axios";

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_guest?: boolean;
}

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isGuest: boolean;

  setAuth: (accessToken: string, user: User, isGuest?: boolean) => void;
  continueAsGuest: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,
      isGuest: false,

      setAuth: (accessToken, user, isGuest = false) => {
        set({
          accessToken,
          user: { ...user, is_guest: isGuest },
          isGuest,
        });

        // Also mirror directly in localStorage for quick synchronous lookups
        localStorage.setItem("access_token", accessToken);
        if (isGuest) {
          sessionStorage.setItem("guest_session", "true");
        } else {
          sessionStorage.removeItem("guest_session");
        }
      },

      continueAsGuest: async () => {
        const res = await axios.post("http://localhost:8000/api/auth/guest");
        const { access_token, user } = res.data;
        get().setAuth(access_token, user, true);
      },

      logout: async () => {
        const { isGuest, accessToken } = get();

        // If guest, request backend cleanup of temporary data
        if (isGuest && accessToken) {
          try {
            await axios.delete("http://localhost:8000/api/auth/guest/cleanup", {
              headers: { Authorization: `Bearer ${accessToken}` },
            });
          } catch {
            // Ignore cleanup failure
          }
        }

        localStorage.removeItem("access_token");
        sessionStorage.removeItem("guest_session");

        set({
          accessToken: null,
          user: null,
          isGuest: false,
        });
      },
    }),
    {
      name: "meeting-ai-auth",
    },
  ),
);

// Clear guest session on tab close if guest mode was active
if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    const isGuest = useAuthStore.getState().isGuest;
    if (isGuest) {
      // Wipes the auth so that upon next reopen, guest session has completely vanished
      localStorage.removeItem("meeting-ai-auth");
      localStorage.removeItem("access_token");
      sessionStorage.removeItem("guest_session");
    }
  });
}
