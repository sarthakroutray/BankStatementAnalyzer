"use client";

import React from "react";
import { Pill } from "./Pill";

interface SectionLabelProps {
  children: React.ReactNode;
  variant?: "yellow" | "black" | "glass" | "dark";
}

export const SectionLabel: React.FC<SectionLabelProps> = ({
  children,
  variant = "glass",
}) => {
  return (
    <div className="inline-flex items-center mb-3">
      <Pill variant={variant} dot>
        {children}
      </Pill>
    </div>
  );
};
