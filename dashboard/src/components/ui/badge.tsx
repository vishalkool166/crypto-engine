import { cva } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
const variants = cva("badge", {
  variants: {
    tone: {
      neutral: "badge-neutral",
      green: "badge-green",
      red: "badge-red",
      amber: "badge-amber",
      blue: "badge-blue",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: string }) {
  return (
    <span
      className={cn(variants({ tone: tone as "neutral" }), className)}
      {...props}
    />
  );
}
