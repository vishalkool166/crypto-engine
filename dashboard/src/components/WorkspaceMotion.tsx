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
        const paths = document.querySelectorAll<SVGPathElement>(
          ".chart-line:not([data-motion])",
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
