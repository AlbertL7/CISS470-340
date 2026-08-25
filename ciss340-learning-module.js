(() => {
    "use strict";

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const progress = document.querySelector(".reading-progress");
    const navLinks = [...document.querySelectorAll(".section-nav a[href^='#']")];
    const sections = navLinks
        .map((link) => document.querySelector(link.getAttribute("href")))
        .filter(Boolean);

    const sectionNav = document.querySelector(".section-nav");
    let sectionList = sectionNav?.querySelector("ul, .section-links");
    if (sectionNav && !sectionList && navLinks.length) {
        sectionList = document.createElement("div");
        sectionList.className = "section-links";
        navLinks.forEach((link) => sectionList.append(link));
        sectionNav.append(sectionList);
    }
    if (sectionNav && sectionList) {
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "nav-toggle";
        toggle.setAttribute("aria-controls", sectionList.id || "chapter-section-list");
        if (!sectionList.id) sectionList.id = "chapter-section-list";

        const mobileNav = window.matchMedia("(max-width: 940px)");
        const setNavState = (expanded) => {
            sectionNav.classList.toggle("is-collapsed", !expanded);
            toggle.setAttribute("aria-expanded", String(expanded));
            toggle.textContent = expanded ? "Hide chapter contents" : "Show chapter contents";
        };
        setNavState(!mobileNav.matches);
        sectionList.before(toggle);

        toggle.addEventListener("click", () => {
            setNavState(toggle.getAttribute("aria-expanded") !== "true");
        });
        mobileNav.addEventListener("change", (event) => setNavState(!event.matches));
        navLinks.forEach((link) => {
            link.addEventListener("click", () => {
                if (mobileNav.matches) setNavState(false);
            });
        });
    }

    function updateProgress() {
        if (!progress) return;
        const available = document.documentElement.scrollHeight - window.innerHeight;
        const percent = available > 0 ? Math.min(100, Math.max(0, window.scrollY / available * 100)) : 100;
        progress.style.width = `${percent}%`;
        progress.setAttribute("aria-valuenow", String(Math.round(percent)));
    }

    updateProgress();
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);

    navLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            const target = document.querySelector(link.getAttribute("href"));
            if (!target) return;
            event.preventDefault();
            target.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
            history.replaceState(null, "", link.getAttribute("href"));
        });
    });

    if ("IntersectionObserver" in window && sections.length) {
        const observer = new IntersectionObserver((entries) => {
            const visible = entries
                .filter((entry) => entry.isIntersecting)
                .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
            if (!visible) return;
            navLinks.forEach((link) => {
                const active = link.getAttribute("href") === `#${visible.target.id}`;
                if (active) link.setAttribute("aria-current", "location");
                else link.removeAttribute("aria-current");
            });
        }, { rootMargin: "-15% 0px -70% 0px", threshold: [0, 0.15, 0.4] });
        sections.forEach((section) => observer.observe(section));
    }

    document.querySelectorAll(".quick-check").forEach((check, index) => {
        const button = check.querySelector("[data-check-answer]");
        const feedback = check.querySelector(".feedback");
        const expected = check.dataset.answer;
        const name = check.querySelector("input[type='radio']")?.name || `check-${index}`;
        if (!button || !feedback || !expected) return;

        button.addEventListener("click", () => {
            const selected = check.querySelector(`input[name="${CSS.escape(name)}"]:checked`);
            feedback.classList.remove("correct", "try-again");
            if (!selected) {
                feedback.textContent = "Choose an answer first, then check your thinking.";
                feedback.classList.add("try-again");
                return;
            }
            const correct = selected.value === expected;
            feedback.textContent = correct ? feedback.dataset.correct : feedback.dataset.retry;
            feedback.classList.add(correct ? "correct" : "try-again");
        });
    });

    document.querySelectorAll(".choice-lab").forEach((lab) => {
        const buttons = [...lab.querySelectorAll("[data-choice]")];
        const panels = [...lab.querySelectorAll("[data-panel]")];
        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                const choice = button.dataset.choice;
                buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
                panels.forEach((panel) => {
                    panel.hidden = panel.dataset.panel !== choice;
                });
            });
        });
    });

    document.querySelectorAll("[data-reveal-target]").forEach((button) => {
        const panel = document.getElementById(button.dataset.revealTarget);
        if (!panel) return;
        button.addEventListener("click", () => {
            const willOpen = panel.hidden;
            panel.hidden = !willOpen;
            button.setAttribute("aria-expanded", String(willOpen));
            button.textContent = willOpen ? "Hide explanation" : "Reveal explanation";
            if (willOpen) {
                if (!panel.hasAttribute("tabindex")) panel.setAttribute("tabindex", "-1");
                panel.focus({ preventScroll: true });
            }
        });
    });
})();
