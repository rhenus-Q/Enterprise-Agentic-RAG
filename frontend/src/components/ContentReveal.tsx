import { type ReactNode, useEffect, useState } from "react";

export const CONTENT_REVEAL_DURATION_MS = 120;

interface ContentRevealProps {
  children: ReactNode;
  className?: string;
  testId?: string;
}

function prefersReducedMotion() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function ContentReveal({ children, className = "", testId }: ContentRevealProps) {
  const [transitioning, setTransitioning] = useState(() => !prefersReducedMotion());
  const classes = [className, transitioning ? "content-reveal" : ""].filter(Boolean).join(" ");

  useEffect(() => {
    if (!transitioning) {
      return;
    }

    const timer = window.setTimeout(() => {
      setTransitioning(false);
    }, CONTENT_REVEAL_DURATION_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [transitioning]);

  return (
    <div className={classes} data-testid={testId} data-transitioning={transitioning}>
      {children}
    </div>
  );
}
