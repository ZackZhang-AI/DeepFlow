"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "soft" | "link";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonClassOptions {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  className?: string;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  fullWidth?: boolean;
}

const baseClasses =
  "inline-flex min-h-11 items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold outline-none transition-all duration-[180ms] ease-out focus-visible:ring-4 disabled:pointer-events-none disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--accent)] text-white shadow-[0_8px_18px_rgba(15,127,131,0.18)] hover:-translate-y-0.5 hover:bg-[var(--accent-hover)] hover:shadow-[0_11px_22px_rgba(15,127,131,0.22)] active:translate-y-0 active:shadow-sm focus-visible:ring-[var(--accent-soft)]",
  secondary:
    "border border-[var(--border)] bg-white text-[var(--ink)] shadow-sm hover:-translate-y-0.5 hover:border-[var(--border-strong)] hover:bg-[var(--surface-muted)] active:translate-y-0 focus-visible:ring-[var(--accent-soft)]",
  ghost:
    "border border-transparent bg-transparent text-[var(--muted)] hover:bg-white hover:text-[var(--ink)] active:bg-[var(--surface-muted)] focus-visible:ring-[var(--accent-soft)]",
  danger:
    "border border-red-200 bg-red-50/80 text-red-600 shadow-sm hover:-translate-y-0.5 hover:border-red-300 hover:bg-red-100/80 hover:text-red-700 hover:shadow-md active:translate-y-0 focus-visible:ring-red-500/15",
  soft:
    "border border-teal-200 bg-teal-50 text-teal-800 hover:-translate-y-0.5 hover:border-teal-300 hover:bg-teal-100 active:translate-y-0 focus-visible:ring-[var(--accent-soft)]",
  link:
    "min-h-0 rounded-lg p-0 text-[var(--muted)] hover:text-[var(--ink)] active:text-slate-700 focus-visible:ring-[var(--accent-soft)]",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-2 text-xs",
  md: "px-4 py-2.5 text-sm",
  lg: "px-6 py-3.5 text-base",
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function getButtonClasses({
  variant = "secondary",
  size = "md",
  fullWidth = false,
  className,
}: ButtonClassOptions = {}) {
  return cx(
    baseClasses,
    variantClasses[variant],
    variant === "link" ? "" : sizeClasses[size],
    fullWidth && "w-full",
    className
  );
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  disabled,
  iconLeft,
  iconRight,
  fullWidth = false,
  children,
  className,
  type = "button",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      className={getButtonClasses({ variant, size, fullWidth, className })}
      {...props}
    >
      {loading ? (
        <span className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
      ) : (
        iconLeft
      )}
      <span>{children}</span>
      {!loading && iconRight}
    </button>
  );
}
