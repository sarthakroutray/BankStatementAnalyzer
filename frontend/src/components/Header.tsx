"use client";

import React from "react";
import { Navbar } from "./Navbar";

interface HeaderProps {
  onOpenUpload: () => void;
  isBackendConnected?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onOpenUpload }) => {
  return <Navbar onOpenUpload={onOpenUpload} />;
};
