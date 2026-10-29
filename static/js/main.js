/* 云端の小窝 —— 一点点交互，不用任何框架 */
(function () {
  "use strict";

  document.documentElement.classList.remove("no-js");

  var header = document.getElementById("siteHeader");
  var navToggle = document.getElementById("navToggle");
  var navLinks = document.getElementById("navLinks");
  var toTop = document.getElementById("toTop");
  var readBar = document.getElementById("readBar");
  var articleBody = document.getElementById("articleBody");

  /* ---------------- 顶部导航：滚动加深阴影 + 移动端菜单 ---------------- */
  function closeMenu() {
    if (!navLinks || !navToggle) return;
    navLinks.classList.remove("is-open");
    navToggle.classList.remove("is-open");
    navToggle.setAttribute("aria-expanded", "false");
  }

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var open = navLinks.classList.toggle("is-open");
      navToggle.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    navLinks.addEventListener("click", function (event) {
      if (event.target.tagName === "A") closeMenu();
    });

    document.addEventListener("click", function (event) {
      if (!navLinks.classList.contains("is-open")) return;
      if (navLinks.contains(event.target) || navToggle.contains(event.target)) return;
      closeMenu();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeMenu();
    });
  }

  /* ---------------- 滚动相关的效果统一在一帧里处理 ---------------- */
  var ticking = false;

  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;

    if (header) header.classList.toggle("is-scrolled", y > 12);
    if (toTop) toTop.classList.toggle("is-visible", y > 420);

    if (readBar && articleBody) {
      var rect = articleBody.getBoundingClientRect();
      var total = rect.height - window.innerHeight * 0.6;
      var passed = -rect.top + window.innerHeight * 0.2;
      var percent = total > 0 ? (passed / total) * 100 : 0;
      readBar.style.width = Math.min(100, Math.max(0, percent)) + "%";
    }

    ticking = false;
  }

  window.addEventListener(
    "scroll",
    function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(onScroll);
    },
    { passive: true }
  );

  onScroll();

  /* ---------------- 滚动到视口时淡入 ---------------- */
  var items = document.querySelectorAll(".reveal");

  if ("IntersectionObserver" in window && items.length) {
    document.documentElement.classList.add("js-reveal");

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.06 }
    );

    items.forEach(function (item) {
      observer.observe(item);
    });

    /* 兜底：回调万一没触发，首屏内容也必须看得见 */
    window.setTimeout(function () {
      items.forEach(function (item) {
        if (item.classList.contains("is-in")) return;
        if (item.getBoundingClientRect().top < window.innerHeight * 1.15) {
          item.classList.add("is-in");
        }
      });
    }, 1200);
  }

  /* ---------------- 回到顶部 ---------------- */
  if (toTop) {
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
})();
