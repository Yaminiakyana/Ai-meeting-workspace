import axios from "axios";
import { useAuthStore } from "../store/authStore";

export const apiClient = axios.create({
  baseURL: "http://localhost:8000/api",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;

  if (
    token &&
    !config.headers.Authorization
  ) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // If receiving 401 Unauthorized outside of auth login/register endpoints, session is invalid/expired
    const requestUrl = error.config?.url || "";
    const isAuthEndpoint = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/register") || requestUrl.includes("/auth/guest");

    if (error.response?.status === 401 && !isAuthEndpoint) {
      console.warn("Session expired or token invalid. Clearing authentication...");
      useAuthStore.getState().logout();

      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        const currentPath = window.location.pathname + window.location.search;
        window.location.href = `/login?from=${encodeURIComponent(currentPath)}`;
      }
    }

    return Promise.reject(error);
  },
);
