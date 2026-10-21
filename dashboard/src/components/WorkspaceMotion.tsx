import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger);
/** Small motion only; trading controls and data never wait for an animation. */
export function WorkspaceMotion() {
  const { pathname } = useLocation();
  useLayoutEffect(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const observer = new MutationObserver(() => animateCharts());
      function animateCharts() {
        const visuals = document.querySelectorAll<HTMLElement>(
          [
            "main .panel:not([data-visual-motion])",
            ".finance-metrics > .metric:not([data-visual-motion])",
            ".metric-grid > .metric:not([data-visual-motion])",
            ".quick-link:not([data-visual-motion])",
            ".india-open-signal:not([data-visual-motion])",
            ".assistant-answer:not([data-visual-motion])",
            ".execution-card:not([data-visual-motion])",
            ".trace-list > *:not([data-visual-motion])",
            ".pwa-banner:not([data-visual-motion])",
            ".data-table tbody tr:not([data-visual-motion])",
            ".trade-detail-pnl:not([data-visual-motion])",
            ".trade-detail-section:not([data-visual-motion])",
            ".dialog-content:not([data-visual-motion])",
          ].join(","),
        );
        visuals.forEach((visual, index) => {
          visual.dataset.visualMotion = "true";
          gsap.fromTo(
            visual,
            { y: 10, opacity: 0.72 },
            {
              y: 0,
              opacity: 1,
              duration: 0.38,
              delay: Math.min(index * 0.035, 0.21),
              ease: "power2.out",
              clearProps: "transform,opacity",
              scrollTrigger: { trigger: visual, start: "top 96%", once: true },
            },
          );
        });
        const reveals = document.querySelectorAll<HTMLElement>(
          "[data-chart-reveal]:not([data-reveal-motion])",
        );
        reveals.forEach((chart, index) => {
          chart.dataset.revealMotion = "true";
          gsap.fromTo(
            chart,
            { clipPath: "inset(0 0 92% 0)", opacity: 0.72 },
            {
              clipPath: "inset(0 0 0% 0)",
              opacity: 1,
              duration: 0.48,
              delay: Math.min(index * 0.06, 0.18),
              ease: "power2.out",
              clearProps: "clipPath,opacity",
              scrollTrigger: { trigger: chart, start: "top 94%", once: true },
            },
          );
        });
        const paths = document.querySelectorAll<SVGPathElement>(
          ".chart-line:not([data-motion]), .analytics-chart path.recharts-area-curve:not([data-motion])",
        );
        paths.forEach((path) => {
          path.dataset.motion = "true";
          const length = path.getTotalLength();
          gsap.fromTo(
            path,
            { strokeDasharray: length, strokeDashoffset: length },
            {
              strokeDashoffset: 0,
              duration: 0.65,
              ease: "power2.out",
              clearProps: "strokeDasharray,strokeDashoffset",
              scrollTrigger: { trigger: path, start: "top 95%", once: true },
            },
          );
          if (path.classList.contains("recharts-area-curve")) {
            gsap.fromTo(
              path,
              { strokeWidth: 2.1 },
              { strokeWidth: 2.8, duration: 0.2, repeat: 1, yoyo: true, delay: 0.52, ease: "sine.inOut", clearProps: "strokeWidth" },
            );
          }
        });
      }
      gsap.fromTo(
        ".page-heading, .research-masthead",
        { y: 6, opacity: 0.7 },
        { y: 0, opacity: 1, duration: 0.25, clearProps: "all" },
      );
      observer.observe(document.getElementById("root")!, {
        childList: true,
        subtree: true,
      });
      animateCharts();
      return () => observer.disconnect();
    });
    return () => media.revert();
  }, [pathname]);
  return null;
}
