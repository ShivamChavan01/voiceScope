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
            title={item.label}
            className={cn(
              "grid h-9 w-10 place-items-center rounded-md transition-colors",
              isActive
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-secondary hover:text-secondary-foreground"
            )}
          >
            <item.icon className="h-4 w-4" />
          </Link>
        );
      })}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom */}
      <button
        title="User"
        className="grid h-9 w-10 place-items-center rounded-md text-muted-foreground hover:bg-secondary hover:text-secondary-foreground transition-colors"
      >
        <User className="h-4 w-4" />
      </button>
    </nav>
  );
}
