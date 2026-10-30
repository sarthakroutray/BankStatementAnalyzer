"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "dark" | "glass" | "yellow" | "charcoal";
  hoverEffect?: boolean;
  float?: boolean;
  children: React.ReactNode;
}

export const GlassCard: React.FC<GlassCardProps> = ({
  variant = "charcoal",
  hoverEffect = false,
  float = false,
  className,
  children,
  ...props
}) => {
  const variantStyles = {
    dark: "bg-onyx/90 border border-white/10 backdrop-blur-2xl shadow-glass",
    charcoal: "bg-charcoal/90 border border-white/10 backdrop-blur-2xl shadow-glass",
    glass: "bg-white/5 border border-white/15 backdrop-blur-2xl shadow-glass",
    yellow: "bg-cyber-yellow/10 border border-cyber-yellow/30 backdrop-blur-xl shadow-glass-yellow",
  };

  return (
    <div
      className={twMerge(
        clsx(
          "rounded-[32px] p-6 transition-all duration-300 ease-fluid",
          variantStyles[variant],
          hoverEffect && "hover:border-white/25 hover:-translate-y-1 hover:shadow-2xl",
          float && "animate-float",
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
