document.querySelectorAll(".doc pre").forEach((pre) => {
  const btn = document.createElement("button");
  btn.className = "copy-btn";
  btn.textContent = "copy";
  btn.addEventListener("click", async () => {
    await navigator.clipboard.writeText(pre.innerText.replace(/copy$/, "").trim());
    btn.textContent = "copied";
    setTimeout(() => (btn.textContent = "copy"), 1200);
  });
  pre.appendChild(btn);
});

const links = Array.from(document.querySelectorAll(".toc a"));
const sections = links
  .map((a) => document.querySelector(a.getAttribute("href")))
  .filter(Boolean);

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      const link = links.find((a) => a.getAttribute("href") === `#${entry.target.id}`);
      if (!link) return;
      if (entry.isIntersecting) {
        links.forEach((a) => a.classList.remove("active"));
        link.classList.add("active");
      }
    });
  },
  { rootMargin: "-20% 0px -70% 0px" }
);

sections.forEach((s) => observer.observe(s));
