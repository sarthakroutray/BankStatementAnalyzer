"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "yellow" | "black" | "outline-black" | "outline-white" | "glass" | "danger";
  size?: "sm" | "md" | "lg";
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "yellow", size = "md", className, children, disabled, ...props }, ref) => {
    const baseStyles =
      "inline-flex items-center justify-center font-sans rounded-full font-semibold transition-all duration-200 ease-fluid cursor-pointer select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-cyber-yellow active:scale-95 disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100";

    const sizeStyles = {
      sm: "text-xs px-3.5 py-1.5 gap-1.5",
      md: "text-xs sm:text-sm px-5 py-2.5 gap-2",
      lg: "text-sm sm:text-base px-7 py-3.5 gap-2.5",
    };

    const variantStyles = {
      yellow:
        "bg-cyber-yellow text-black hover:bg-yellow-300 shadow-md hover:shadow-yellow-glow hover:scale-105",
      black:
        "bg-black text-white hover:bg-neutral-900 shadow-md hover:shadow-black/50 hover:scale-105",
      "outline-black":
        "border-2 border-black/25 text-black hover:bg-black/5 hover:border-black/50 hover:scale-105",
      "outline-white":
        "border border-white/20 text-white hover:bg-white/10 hover:border-white/40 hover:scale-105",
      glass:
        "bg-white/10 text-white hover:bg-white/20 border border-white/20 backdrop-blur-xl shadow-glass hover:scale-105",
      danger:
        "bg-danger/10 text-danger hover:bg-danger/20 border border-danger/30 hover:scale-105",
    };

    return (
      <button
        ref={ref}
        disabled={disabled}
        className={twMerge(clsx(baseStyles, sizeStyles[size], variantStyles[variant], className))}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
