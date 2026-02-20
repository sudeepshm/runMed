"use client";

import { useEffect, useRef } from "react";

export default function Parallax() {
  const layer1 = useRef<HTMLDivElement | null>(null);
  const layer2 = useRef<HTMLDivElement | null>(null);
  const layer3 = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let raf = 0;

    const handle = () => {
      const scrollY = window.scrollY || 0;
      const w = window.innerWidth;
      const h = window.innerHeight;

      // subtle vertical parallax based on scroll
      if (layer1.current) layer1.current.style.transform = `translate3d(0, ${scrollY * 0.05}px, 0)`;
      if (layer2.current) layer2.current.style.transform = `translate3d(0, ${scrollY * 0.09}px, 0)`;
      if (layer3.current) layer3.current.style.transform = `translate3d(0, ${scrollY * 0.14}px, 0)`;

      raf = 0;
    };

    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(handle);
    };

    const onMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) - 0.5;
      const y = (e.clientY / window.innerHeight) - 0.5;
      if (layer1.current) layer1.current.style.transform += ` translate3d(${x * 12}px, ${y * 6}px, 0)`;
      if (layer2.current) layer2.current.style.transform += ` translate3d(${x * 8}px, ${y * 4}px, 0)`;
      if (layer3.current) layer3.current.style.transform += ` translate3d(${x * 4}px, ${y * 2}px, 0)`;
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("mousemove", onMove);

    // initial position
    handle();

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("mousemove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      <div ref={layer1} className="absolute -left-40 -top-20 w-[700px] h-[700px] rounded-full blur-3xl opacity-30"
        style={{ background: "radial-gradient(circle at 20% 20%, rgba(59,130,246,0.25), transparent 30%), radial-gradient(circle at 80% 80%, rgba(167,139,250,0.18), transparent 35%)" }} />

      <div ref={layer2} className="absolute right-[-120px] top-24 w-[520px] h-[520px] rounded-full blur-2xl opacity-25"
        style={{ background: "radial-gradient(circle at 30% 30%, rgba(34,211,238,0.16), transparent 30%), radial-gradient(circle at 70% 70%, rgba(59,130,246,0.12), transparent 40%)" }} />

      <div ref={layer3} className="absolute left-1/2 top-[420px] w-[900px] h-[420px] -translate-x-1/2 rounded-t-full blur-2xl opacity-12"
        style={{ background: "linear-gradient(180deg, rgba(10,14,26,0) 0%, rgba(10,14,26,0.6) 100%)" }} />
    </div>
  );
}
