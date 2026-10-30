"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface PillProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "yellow" | "black" | "dark" | "glass" | "success" | "danger" | "neutral";
  dot?: boolean;
  dotColor?: string;
  children: React.ReactNode;
}

export const Pill: React.FC<PillProps> = ({
  variant = "glass",
  dot = false,
  dotColor,
  className,
  children,
  ...props
}) => {
  const variantStyles = {
    yellow: "bg-cyber-yellow text-black border border-yellow-400 font-bold",
    black: "bg-black/90 text-white border border-white/20 font-semibold",
    dark: "bg-deep-gray text-white border border-white/10 font-medium",
    glass: "bg-white/10 text-white border border-white/20 backdrop-blur-md font-medium",
    success: "bg-success/15 text-success border border-success/30 font-semibold",
    danger: "bg-danger/15 text-danger border border-danger/30 font-semibold",
    neutral: "bg-white/5 text-neutral-300 border border-white/10 font-medium",
  };

  return (
    <span
      className={twMerge(
        clsx(
          "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] uppercase tracking-widest font-mono select-none",
          variantStyles[variant],
          className
        )
      )}
      {...props}
    >
      {dot && (
        <span
          className={clsx(
            "w-1.5 h-1.5 rounded-full shrink-0",
            dotColor || (variant === "yellow" ? "bg-black" : "bg-cyber-yellow")
          )}
        />
      )}
      {children}
    </span>
  );
};
