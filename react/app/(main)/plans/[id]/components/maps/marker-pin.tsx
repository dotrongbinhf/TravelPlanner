import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface MarkerPinProps {
  width?: number;
  height?: number;
  color: string;
  children?: ReactNode;
  className?: string;
  active?: boolean;
}

export default function MarkerPin({
  width = 30,
  height = 42,
  color,
  children,
  className,
  active,
}: MarkerPinProps) {
  return (
    <div
      className={cn("relative flex items-center justify-center", className)}
      style={{ width, height }}
    >
      <svg
        width={width}
        height={height}
        viewBox="0 0 30 42"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={cn(
          "transition-all duration-300 drop-shadow-md",
          active && "drop-shadow-xl",
        )}
      >
        <path
          d="M15 0.5C7.02 0.5 0.5 7.02 0.5 15C0.5 25.5 15 41.5 15 41.5C15 41.5 29.5 25.5 29.5 15C29.5 7.02 22.98 0.5 15 0.5Z"
          fill={color}
          stroke="white"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
      <div
        className="absolute flex items-center justify-center text-white"
        style={{
          top: "35.7%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      >
        {children}
      </div>
    </div>
  );
}
