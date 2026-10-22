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
            ".atelier-step:not([data-visual-motion])",
            ".atelier-evidence-numbers > div:not([data-visual-motion])",
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
      // Story reveals are editorial, not decorative trading-number animation.
      // No reliance on GSAP for the initial content visibility or controls.
      const studioHero = document.querySelector(".atelier-hero-copy");
      if (studioHero) {
        const timeline = gsap.timeline({defaults:{ease:"power3.out"}});
        timeline.fromTo(".atelier-overline", {opacity:0,y:12}, {opacity:1,y:0,duration:.65})
          .fromTo(".atelier-hero h1", {opacity:0,y:33}, {opacity:1,y:0,duration:1.1},"-=.32")
          .fromTo(".atelier-hero-underline, .atelier-hero-intro, .atelier-hero-cta", {opacity:0,y:15},{opacity:1,y:0,duration:.65,stagger:.11},"-=.55")
          .fromTo(".atelier-field", {opacity:0,x:28},{opacity:1,x:0,duration:1.15},"-=1.0");
      }
      if (document.querySelector(".atelier-manifesto h2")) {
        gsap.fromTo(".atelier-manifesto h2, .atelier-manifesto p",
          {opacity:.72,y:24},{opacity:1,y:0,duration:.95,stagger:.13,ease:"power2.out",clearProps:"all",
          scrollTrigger:{trigger:".atelier-manifesto",start:"top 80%",once:true}});
      }
      if (document.querySelector(".atelier-outro h2")) {
        gsap.fromTo(".atelier-outro h2",{opacity:.65,y:24},{opacity:1,y:0,duration:1,ease:"power2.out",clearProps:"all",
          scrollTrigger:{trigger:".atelier-outro",start:"top 80%",once:true}});
      }
      gsap.fromTo(
        ".page-heading, .research-masthead",
        { y: 6, opacity: 0.7 },
        { y: 0, opacity: 1, duration: 0.25, clearProps: "all" },
      );
      // Studio 3.3: choreographed entrance and scroll-driven system explanation.
      // All content is visible without JS, and reduced-motion users skip this branch.
      if (document.querySelector(".studio-hero")) {
        gsap.timeline({ defaults: { ease: "power3.out" } })
          .fromTo(".studio-hero-meta", {opacity:0,y:-12},{opacity:1,y:0,duration:.7})
          .fromTo(".studio-hero h1",{opacity:0,y:38},{opacity:1,y:0,duration:1.25},"-=.36")
          .fromTo(".studio-hero-lede",{opacity:0,y:22},{opacity:1,y:0,duration:.8},"-=.55")
          .fromTo(".studio-hero-actions>*",{opacity:0,y:17},{opacity:1,y:0,duration:.7,stagger:.11},"-=.45")
          .fromTo(".studio-figure",{opacity:.35,y:45,scale:.97},{opacity:1,y:0,scale:1,duration:1.2},"-=.48");
        gsap.fromTo(".studio-thesis h2",{opacity:.26,y:55},{opacity:1,y:0,duration:1,ease:"none",
          scrollTrigger:{trigger:".studio-thesis",start:"top 84%",end:"top 28%",scrub:1.2}});
        gsap.fromTo(".studio-large-bars span",{y:80,opacity:0,rotate:-20},{y:0,opacity:.68,rotate:0,stagger:.11,duration:1,ease:"power2.out",
          scrollTrigger:{trigger:".studio-thesis",start:"top 72%",end:"top 20%",scrub:1.2}});
        const steps = gsap.utils.toArray<HTMLElement>(".studio-narrative-step");
        steps.forEach((step,index) => {
          const label = step.querySelector("h3");
          if (label) gsap.fromTo(label,{y:36,opacity:.5},{y:0,opacity:1,ease:"none",duration:1,
            scrollTrigger:{trigger:step,start:"top 85%",end:"top 46%",scrub:1.1}});
          ScrollTrigger.create({trigger:step,start:"top 60%",end:"bottom 40%",
            onEnter:()=>step.classList.add("is-current"),
            onEnterBack:()=>step.classList.add("is-current"),
            onLeave:()=>step.classList.remove("is-current"),
            onLeaveBack:()=>step.classList.remove("is-current")});
        });
        gsap.fromTo(".studio-stage-lines i",{scaleX:.14,opacity:.15},{scaleX:1,opacity:.8,stagger:.15,ease:"none",
          scrollTrigger:{trigger:".studio-narrative",start:"top 72%",end:"bottom 55%",scrub:1.7}});
        gsap.fromTo(".studio-evidence-stats > div",{opacity:.3,y:32},{opacity:1,y:0,stagger:.13,duration:.85,ease:"none",
          scrollTrigger:{trigger:".studio-evidence-stats",start:"top 82%",end:"top 48%",scrub:1.1}});
        gsap.fromTo(".studio-finale h2",{opacity:.3,y:65},{opacity:1,y:0,ease:"none",
          scrollTrigger:{trigger:".studio-finale",start:"top 80%",end:"top 28%",scrub:1.2}});
      }
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
