"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

type HoverTipProps = {
  tip: ReactNode;
  children: ReactNode;
  placement?: "top" | "bottom";
  align?: "center" | "end";
  tapToToggle?: boolean;
  className?: string;
  tipClassName?: string;
};

const TIP_Z_INDEX = 40;

function usePrefersHover() {
  const [prefersHover, setPrefersHover] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia("(hover: hover)");
    const update = () => setPrefersHover(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return prefersHover;
}

const TIP_BASE_CLASS =
  "rounded-sm border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-[#252019] px-2.5 py-1.5 text-left text-[length:var(--type-sm)] leading-snug text-zinc-600 dark:text-zinc-300 shadow-[3px_3px_0_0_var(--color-border-tertiary)] transition-all duration-150";

function tipVisibilityClass(open: boolean) {
  return open
    ? "opacity-100 translate-y-0 pointer-events-auto"
    : "opacity-0 translate-y-0.5 pointer-events-none";
}

function portalFixedStyle(
  coords: DOMRect,
  placement: "top" | "bottom",
  align: "center" | "end"
): CSSProperties {
  const gap = 8;
  const base: CSSProperties = {
    position: "fixed",
    zIndex: TIP_Z_INDEX,
    fontFamily: "'Nunito'",
    fontWeight: 400,
  };

  if (placement === "top" && align === "end") {
    return {
      ...base,
      top: coords.top - gap,
      right: window.innerWidth - coords.right,
      transform: "translateY(-100%)",
    };
  }
  if (placement === "top" && align === "center") {
    return {
      ...base,
      top: coords.top - gap,
      left: coords.left + coords.width / 2,
      transform: "translate(-50%, -100%)",
    };
  }
  if (placement === "bottom" && align === "end") {
    return {
      ...base,
      top: coords.bottom + gap,
      right: window.innerWidth - coords.right,
    };
  }
  return {
    ...base,
    top: coords.bottom + gap,
    left: coords.left + coords.width / 2,
    transform: "translateX(-50%)",
  };
}

export default function HoverTip({
  tip,
  children,
  placement = "top",
  align = "center",
  tapToToggle = true,
  className = "",
  tipClassName = "",
}: HoverTipProps) {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const prefersHover = usePrefersHover();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<DOMRect | null>(null);

  useEffect(() => {
    queueMicrotask(() => setMounted(true));
  }, []);

  const syncCoords = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    setCoords(el.getBoundingClientRect());
  }, []);

  const show = useCallback(() => {
    syncCoords();
    setOpen(true);
  }, [syncCoords]);

  const hide = useCallback(() => setOpen(false), []);

  const toggle = useCallback(() => {
    if (open) hide();
    else show();
  }, [open, hide, show]);

  const onTriggerClick = useCallback(
    (e: React.MouseEvent) => {
      if (prefersHover) return;
      e.preventDefault();
      e.stopPropagation();
      toggle();
    },
    [prefersHover, toggle]
  );

  useEffect(() => {
    if (!open || prefersHover || !tapToToggle) return;
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target)) return;
      hide();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, prefersHover, tapToToggle, hide]);

  useEffect(() => {
    if (!open) return;
    const onUpdate = () => syncCoords();
    window.addEventListener("scroll", onUpdate, true);
    window.addEventListener("resize", onUpdate);
    return () => {
      window.removeEventListener("scroll", onUpdate, true);
      window.removeEventListener("resize", onUpdate);
    };
  }, [open, syncCoords]);

  if (mounted) {
    const fixedStyle = coords
      ? portalFixedStyle(coords, placement, align)
      : { position: "fixed" as const, visibility: "hidden" as const };

    return (
      <>
        <span
          ref={triggerRef}
          className={`inline-flex ${className}`}
          onMouseEnter={prefersHover ? show : undefined}
          onMouseLeave={prefersHover ? hide : undefined}
          onFocus={show}
          onBlur={prefersHover ? hide : undefined}
          onClick={onTriggerClick}
        >
          {children}
        </span>
        {createPortal(
          <span
            role="tooltip"
            style={fixedStyle}
            className={`${TIP_BASE_CLASS} w-max max-w-[260px] ${tipVisibilityClass(open)} ${tipClassName}`}
          >
            {tip}
          </span>,
          document.body
        )}
      </>
    );
  }

  return <span className={`inline-flex ${className}`}>{children}</span>;
}
