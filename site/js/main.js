/* ============================================================
   WenZi — GitHub Pages Script
   Scroll-fade animation + GitHub Release version fetch
   ============================================================ */

(function () {
  "use strict";

  // ---------- Intersection Observer for fade-in ----------
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  document.querySelectorAll(".fade-in").forEach((el) => observer.observe(el));

  // ---------- Fetch latest release from GitHub API ----------
  const REPO = "Airead/WenZi";
  const versionBadge = document.getElementById("version-badge");
  const downloadBtn = document.getElementById("download-btn");

  if (versionBadge || downloadBtn) {
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((res) => {
        if (!res.ok) throw new Error(res.status);
        return res.json();
      })
      .then((release) => {
        const tag = release.tag_name; // e.g. "v0.0.5"

        if (versionBadge) {
          versionBadge.textContent = `Latest: ${tag}`;
        }

        if (downloadBtn) {
          // Find .dmg or .app.zip asset
          const asset = release.assets.find(
            (a) => a.name.endsWith(".dmg") || a.name.endsWith(".zip")
          );
          if (asset) {
            downloadBtn.href = asset.browser_download_url;
          } else {
            downloadBtn.href = release.html_url;
          }
        }
      })
      .catch(() => {
        // Silently fall back — badge keeps default text, button keeps Releases link
      });
  }
})();
