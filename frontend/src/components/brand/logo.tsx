import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/utils";

/** RoadLens logo mark: a road converging inside a lens aperture. */
export function LogoMark({
  className,
  ...props
}: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className={cn("h-6 w-6", className)}
      {...props}
    >
      <rect width="32" height="32" rx="8" fill="hsl(226 62% 42%)" />
      <circle cx="16" cy="16" r="10.5" stroke="white" strokeWidth="1.6" opacity="0.55" />
      <path d="M12.5 24 L15 8 H17 L19.5 24 Z" fill="white" />
      <path
        d="M15.85 21.5h0.3M15.7 17.8h0.6M15.55 14.1h0.9"
        stroke="hsl(226 62% 42%)"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({
  className,
  dark = false,
}: {
  className?: string;
  dark?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span
        className={cn(
          "text-[15px] font-semibold tracking-tight",
          dark ? "text-white" : "text-foreground",
        )}
      >
        {BRAND.name}
      </span>
    </span>
  );
}
