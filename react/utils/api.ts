import axios, {
  AxiosRequestHeaders,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { TokenStorage } from "./tokenStorage";
import { refreshToken } from "@/api/auth/auth";
import toast from "react-hot-toast";

const SKIP_AUTH_PATHS = ["/api/auth/login", "/api/auth/signup"];

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_ENDPOINT,
  responseType: "json",
  withCredentials: true,
  timeout: 5000 * 60,
});

const requestHandler = (request: InternalAxiosRequestConfig) => {
  request.headers = request.headers || ({} as AxiosRequestHeaders);

  const accessToken = TokenStorage.getAccessToken();
  if (
    accessToken !== null &&
    !SKIP_AUTH_PATHS.some((path) => request.url?.includes(path))
  ) {
    request.headers.Authorization = `Bearer ${accessToken}`;
  }

  request.headers["Client-Host-Name"] = window.location.hostname;
  request.headers["Client-Device"] = "WEB";
  request.headers["Client-Device-Type"] = "WEB";

  return request;
};

const successHandler = (response: AxiosResponse) => response;

let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (token) {
      prom.resolve(token);
    } else {
      prom.reject(error);
    }
  });

  failedQueue = [];
};

const errorHandler = async (error: any) => {
  const originalRequest = error.config;

  if (error.response?.status !== 401 || originalRequest._retry) {
    return Promise.reject(error);
  }

  if (error && error.status === 401) {
    if (error?.config?.url === "/api/auth/refresh-token") {
      TokenStorage.removeAccessToken();
      window.location.href = "/login";
      return;
    }

    if (!isRefreshing) {
      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const newAccessTokenResponse = await refreshToken();
        const newAccessToken = newAccessTokenResponse.accessToken;

        if (newAccessToken) {
          TokenStorage.setAccessToken(newAccessToken);
          processQueue(null, newAccessToken);

          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          return axios(originalRequest);
        } else {
          failedQueue = [];
          toast.error("Login session expired!");
          setTimeout(() => {
            TokenStorage.removeAccessToken();
            window.location.href = "/login";
          }, 3000);
          return;
        }
      } catch (err) {
        processQueue(err, null);
        toast.error("Login session expired!");
        setTimeout(() => {
          TokenStorage.removeAccessToken();
          window.location.href = "/login";
        }, 3000);
        return Promise.reject(error);
      } finally {
        isRefreshing = false;
      }
    }
    return new Promise(function (resolve, reject) {
      failedQueue.push({
        resolve: (token: string) => {
          originalRequest._retry = true;
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(axios(originalRequest));
        },
        reject: (err: any) => {
          reject(err);
        },
      });
    });
  }

  return Promise.reject(error);
};

API.interceptors.request.use(requestHandler);
API.interceptors.response.use(successHandler, errorHandler);

export default API;
