import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth";

const http = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

/** 刷新专用，避免与本实例的响应拦截器互相触发 */
const refreshHttp = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

http.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

http.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _djRetry?: boolean };
    const status = error.response?.status;
    if (status !== 401 || !original || original._djRetry) {
      return Promise.reject(error);
    }
    const url = original.url || "";
    if (url.includes("/auth/login") || url.includes("/auth/register") || url.includes("/auth/refresh")) {
      return Promise.reject(error);
    }
    const auth = useAuthStore();
    const rt = auth.refreshToken;
    if (!rt) {
      return Promise.reject(error);
    }
    original._djRetry = true;
    try {
      const { data } = await refreshHttp.post<{ access_token: string }>(
        "/auth/refresh",
        {},
        { headers: { Authorization: `Bearer ${rt}` } }
      );
      auth.setAccessToken(data.access_token);
      original.headers.Authorization = `Bearer ${data.access_token}`;
      return http(original);
    } catch {
      auth.clear();
      return Promise.reject(error);
    }
  }
);

export default http;
