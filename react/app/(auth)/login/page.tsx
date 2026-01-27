"use client";

import { login } from "@/api/auth/auth";
import { useAppContext } from "@/contexts/AppContext";
import { TokenStorage } from "@/utils/tokenStorage";
import { AxiosError } from "axios";
import { Eye, EyeOff } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export default function Login() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const { user, setUser } = useAppContext();

  // useEffect(() => {
  //   if (TokenStorage.getAccessToken()) {
  //     router.push("/");
  //   }
  // }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // setLoading(true);

    try {
      const response = await login({ username, password });
      TokenStorage.setAccessToken(response.accessToken);
      setUser(response.user);
      toast.success("Login successful!");
      router.replace("/");
    } catch (error) {
      console.error("Login failed:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data ?? "Unexpected Error");
      } else {
        toast.error("Unexpected Login Error");
      }
    }
    // finally {
    //   setLoading(false);
    // }
  };

  return (
    <div className="flex h-[90%] w-[80%] items-center justify-center bg-white rounded-2xl shadow-2xl overflow-hidden">
      <div className="hidden md:block h-full w-1/2">
        <img
          src="/images/auth/login-thumbnail.jpg"
          alt="Login Thumbnail"
          className="h-full w-full object-cover"
        />
      </div>

      <div className="w-full md:w-1/2 h-full flex flex-col justify-center px-8 lg:px-16 py-12">
        <div className="max-w-md mx-auto w-full h-full flex flex-col justify-between">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">
              Welcome Back!
            </h1>
            <p className="text-gray-500">Login to continue</p>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="username"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="username"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                required
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={showPassword ? "password" : "••••••••"}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all pr-12"
                  required
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Remember & Forgot Password */}
            {/* <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-600">
                  Remember me
                </span>
              </label>
              <a
                href="/forgot-password"
                className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
              >
                Forgot password?
              </a>
            </div> */}

            {/* Submit Button */}
            <button
              type="submit"
              className="w-full py-3 px-4 bg-blue-500 hover:bg-blue-700 cursor-pointer text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            >
              Login
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center">
            <div className="flex-1 border-t border-gray-300"></div>
            <span className="px-4 text-sm text-gray-500">or</span>
            <div className="flex-1 border-t border-gray-300"></div>
          </div>

          {/* Social Login */}
          <div className="space-y-3">
            <button
              type="button"
              className="cursor-pointer w-full py-3 px-4 border border-gray-300 rounded-lg flex items-center justify-center gap-3 hover:bg-gray-100 transition-all"
            >
              <Image
                src="/svg/google-icon.svg"
                alt="Google icon"
                width={20}
                height={20}
              />
              <span className="text-gray-700 font-medium">
                Login with Google
              </span>
            </button>
          </div>

          {/* Register Link */}
          <p className="text-center text-gray-600">
            Don't have an account?{" "}
            <a
              href="/register"
              className="text-blue-600 hover:text-blue-800 font-semibold hover:underline"
            >
              Register now!
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
