import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const accessToken =
    localStorage.getItem("access_token") || sessionStorage.getItem("access_token");
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthEndpoint = typeof error?.config?.url === "string" && error.config.url.includes("/api/v1/auth/");

    if (error.response?.status === 401 && !isAuthEndpoint && window.location.pathname !== "/signin") {
      localStorage.removeItem("access_token");
      sessionStorage.removeItem("access_token");
      window.location.assign("/signin");
    }

    return Promise.reject(error);
  },
);
