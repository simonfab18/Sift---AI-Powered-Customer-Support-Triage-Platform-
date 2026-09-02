"use client";

import { useEffect } from "react";

export function ScrollReveal() {
  useEffect(() => {
    const progress = document.querySelector<HTMLElement>(".scroll-progress");
    const revealItems = Array.from(document.querySelectorAll<HTMLElement>(".reveal-up, .feature-card, .resource-card, .detail-panel, .pricing-card, .workflow-detail-step, .product-content-card"));

    const setProgress = () => {
      if (!progress) return;
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const amount = maxScroll > 0 ? window.scrollY / maxScroll : 0;
      progress.style.transform = `scaleX(${Math.min(1, Math.max(0, amount))})`;
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.12 },
    );

    revealItems.forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${Math.min(index % 6, 5) * 70}ms`);
      observer.observe(item);
    });

    setProgress();
    window.addEventListener("scroll", setProgress, { passive: true });
    window.addEventListener("resize", setProgress);

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", setProgress);
      window.removeEventListener("resize", setProgress);
    };
  }, []);

  return <div className="scroll-progress" aria-hidden="true" />;
}