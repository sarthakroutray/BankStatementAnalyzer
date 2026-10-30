"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  rounded?: "pill" | "panel" | "sm";
}

export const Skeleton: React.FC<SkeletonProps> = ({
  rounded = "panel",
  className,
  ...props
}) => {
  const roundedStyles = {
    pill: "rounded-full",
    panel: "rounded-[32px]",
    sm: "rounded-lg",
  };

  return (
    <div
      className={twMerge(
        clsx(
          "bg-white/5 border border-white/5 animate-pulse",
          roundedStyles[rounded],
          className
        )
      )}
      {...props}
    />
  );
};
