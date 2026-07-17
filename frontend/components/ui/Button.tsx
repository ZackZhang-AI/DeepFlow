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
    "bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-[0_14px_30px_rgba(8,145,178,0.28)] hover:-translate-y-0.5 hover:shadow-[0_18px_40px_rgba(37,99,235,0.26)] active:translate-y-0 focus-visible:ring-cyan-500/20",
  secondary:
    "border border-slate-200 bg-white/80 text-slate-700 shadow-sm hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:text-slate-950 hover:shadow-md active:translate-y-0 focus-visible:ring-slate-500/10",
  ghost:
    "border border-transparent bg-transparent text-slate-600 hover:-translate-y-0.5 hover:border-slate-200 hover:bg-white/70 hover:text-slate-950 active:translate-y-0 focus-visible:ring-cyan-500/10",
  danger:
    "border border-red-200 bg-red-50/80 text-red-600 shadow-sm hover:-translate-y-0.5 hover:border-red-300 hover:bg-red-100/80 hover:text-red-700 hover:shadow-md active:translate-y-0 focus-visible:ring-red-500/15",
  soft:
    "border border-cyan-200 bg-cyan-50/80 text-cyan-800 shadow-sm hover:-translate-y-0.5 hover:border-cyan-300 hover:bg-white hover:shadow-md active:translate-y-0 focus-visible:ring-cyan-500/15",
  link:
    "min-h-0 rounded-lg p-0 text-slate-500 hover:text-slate-950 active:text-slate-700 focus-visible:ring-cyan-500/10",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-2 text-xs",
  md: "px-4 py-2.5 text-sm",
  lg: "rounded-2xl px-6 py-3.5 text-base",
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
