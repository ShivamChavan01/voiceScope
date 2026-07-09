"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, List, Settings, User } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutGrid },
  { href: "/runs", label: "Runs", icon: List },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col items-center border-r border-border bg-background py-3 gap-1">
      {/* Logo */}
      <div className="mb-4 grid h-7 w-7 place-items-center rounded-md bg-primary">
        <div className="h-[10px] w-[10px] rounded-sm border-2 border-background" />
      </div>

      {/* Nav buttons */}
      {navItems.map((item) => {
        const isActive =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "sidebar-nav-item",
              isActive && "sidebar-nav-active"
            )}
          >
            <item.icon className="h-4 w-4" />
            <span className="sidebar-nav-label">{item.label}</span>
          </Link>
        );
      })}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom */}
      <button
        className="sidebar-nav-item"
      >
        <User className="h-4 w-4" />
      </button>
    </nav>
  );
}
