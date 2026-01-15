"use client";

import Link from "next/link";
import { Home, Map, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-blue-50 via-white to-cyan-50 flex items-center justify-center p-4">
      <div className="text-center max-w-2xl mx-auto">
        {/* Illustration */}
        <div className="relative mb-8">
          {/* Map Icon Background */}
          <div className="w-48 h-48 mx-auto relative">
            <div className="absolute inset-0 bg-blue-100 rounded-full animate-pulse"></div>
            <div className="absolute inset-4 bg-blue-200 rounded-full"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <Map className="w-20 h-20 text-blue-500" />
            </div>
            {/* Lost Pin */}
            <div className="absolute -top-2 -right-2 bg-red-500 rounded-full p-2 shadow-lg animate-bounce">
              <span className="text-white text-xl w-[24px] h-[24px] flex items-center justify-center">
                ?
              </span>
            </div>
          </div>
        </div>

        {/* 404 Text */}
        <h1 className="text-8xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-500 mb-4">
          404
        </h1>

        {/* Message */}
        <h2 className="text-3xl font-bold text-gray-800 mb-4">
          Oops! Bạn đã đi lạc rồi!
        </h2>
        <p className="text-lg text-gray-600 mb-8 max-w-md mx-auto">
          Có vẻ như trang bạn đang tìm kiếm không tồn tại hoặc đã được di chuyển
          đến một địa điểm mới.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl shadow-md hover:shadow-lg transition-all duration-200"
          >
            <Home className="w-5 h-5" />
            Về trang chủ
          </Link>
          <button
            onClick={() => history.back()}
            className="cursor-pointer inline-flex items-center justify-center gap-2 px-6 py-3 bg-white hover:bg-gray-50 text-gray-700 font-semibold rounded-xl shadow-md hover:shadow-lg border border-gray-200 transition-all duration-200"
          >
            <ArrowLeft className="w-5 h-5" />
            Quay lại
          </button>
        </div>

        {/* Decorative Elements */}
        <div className="mt-12 flex justify-center gap-2">
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: "0ms" }}
          ></span>
          <span
            className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
            style={{ animationDelay: "150ms" }}
          ></span>
          <span
            className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: "300ms" }}
          ></span>
        </div>
      </div>
    </div>
  );
}
