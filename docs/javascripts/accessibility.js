/* Complete the Material controls and overflow regions with native keyboard access. */
(() => {
  const german = document.documentElement.lang.startsWith("de");
  const words = german ? {
    search: "Dokumentation durchsuchen", closeSearch: "Suche schließen",
    navigation: "Navigation öffnen oder schließen", menu: "Navigation", closeNavigation: "Navigation schließen", back: "Zurück zur übergeordneten Navigation",
    light: "Helles Farbschema", dark: "Dunkles Farbschema",
    switchLight: "Zum hellen Farbschema wechseln", switchDark: "Zum dunklen Farbschema wechseln",
    table: "Tabelle", code: "Codeblock", scroll: "horizontal mit den Pfeiltasten scrollen"
  } : {
    search: "Search documentation", closeSearch: "Close search",
    navigation: "Open or close navigation", menu: "Navigation", closeNavigation: "Close navigation", back: "Back to parent navigation",
    light: "Light theme", dark: "Dark theme",
    switchLight: "Switch to light theme", switchDark: "Switch to dark theme",
    table: "Table", code: "Code block", scroll: "scroll horizontally with the arrow keys"
  };

  const search = document.querySelector(".md-search[role='dialog']");
  if (search) {
    search.id ||= "guide-search";
    search.setAttribute("aria-label", words.search);
  }

  document.querySelectorAll(".md-option[data-md-color-scheme]").forEach(input => {
    const light = input.dataset.mdColorScheme === "default";
    input.setAttribute("aria-label", light ? words.light : words.dark);
    const label = input.nextElementSibling;
    if (label?.tagName === "LABEL") label.title = light ? words.switchDark : words.switchLight;
  });

  const primary = document.querySelector(".md-sidebar--primary");
  if (primary) primary.id ||= "guide-navigation";
  const selectors = ".md-header__inner > label[for='__drawer'], .md-header__inner > label[for='__search'], " +
    ".md-search__icon[for='__search'], .md-nav__link[for], .md-nav__title[for]";
  document.querySelectorAll(selectors).forEach(label => {
    // The drawer's title contains a real home link: avoid nesting it in a button.
    if (label.querySelector("a")) return;
    const input = document.getElementById(label.htmlFor);
    if (!input) return;
    const button = document.createElement("button");
    // Retain Material's attributes (including `for`) as CSS hooks. Native buttons
    // supply the keyboard behaviour and semantics that a label cannot provide.
    for (const attribute of label.attributes) button.setAttribute(attribute.name, attribute.value);
    button.type = "button";
    button.innerHTML = label.innerHTML;
    button.dataset.guideToggle = input.id;
    label.replaceWith(button);
    const navigationLink = label.classList.contains("md-nav__link");
    const panel = input.id === "__search" ? search : input.id === "__drawer" ? primary :
      input.parentElement.querySelector(":scope > nav.md-nav");
    if (panel) {
      panel.id ||= "guide-panel-" + input.id;
      button.setAttribute("aria-controls", panel.id);
    }
    button.tabIndex = 0;
    if (input.id === "__search") {
      button.setAttribute("aria-label", label.classList.contains("md-search__icon") ? words.closeSearch : words.search);
      if (button.classList.contains("md-header__button")) button.setAttribute("aria-haspopup", "dialog");
      else {
        // On desktop this icon is a decorative magnifier, not a close control.
        const compact = window.matchMedia("(max-width: 59.984375em)");
        const searchIcon = () => {
          button.tabIndex = compact.matches ? 0 : -1;
          if (compact.matches) button.removeAttribute("aria-hidden");
          else button.setAttribute("aria-hidden", "true");
        };
        compact.addEventListener("change", searchIcon);
        searchIcon();
      }
    } else if (input.id === "__drawer") button.setAttribute("aria-label", words.navigation);
    else if (!navigationLink) button.setAttribute("aria-label", words.back + ": " + label.textContent.trim());
    const expanded = () => button.setAttribute("aria-expanded", String(input.checked));
    expanded();
    input.addEventListener("change", expanded);
    button.addEventListener("click", () => {
      input.click();
      expanded();
      if (!input.checked && !button.classList.contains("md-header__button")) {
        requestAnimationFrame(() => document.querySelector(`[data-guide-toggle='${input.id}'].md-header__button, [data-guide-toggle='${input.id}'].md-nav__link`)?.focus());
      }
    });
  });

  const searchToggle = document.getElementById("__search");
  if (search && searchToggle) {
    const trigger = document.querySelector(".md-header__button[data-guide-toggle='__search']");
    const query = search.querySelector(".md-search__input");
    const compact = window.matchMedia("(max-width: 59.984375em)");
    searchToggle.addEventListener("change", () => {
      if (searchToggle.checked) {
        if (compact.matches) search.setAttribute("aria-modal", "true");
        requestAnimationFrame(() => query?.focus());
      } else {
        search.removeAttribute("aria-modal");
        if (compact.matches) requestAnimationFrame(() => trigger?.focus());
      }
    });
    document.addEventListener("keydown", event => {
      if (!searchToggle.checked || !compact.matches) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        searchToggle.click();
        trigger?.focus();
      } else if (event.key === "Tab") {
        const elements = [...search.querySelectorAll("input, button, a[href], [tabindex='0']")].filter(element =>
          element.tabIndex >= 0 && !element.disabled && element.getClientRects().length && getComputedStyle(element).visibility === "visible");
        if (elements.length) {
          // Keep focus in the mobile dialog. Result selection retains Material's
          // existing ArrowUp/ArrowDown/Enter navigation and roving tabindex.
          event.preventDefault();
          event.stopImmediatePropagation();
          const index = elements.indexOf(document.activeElement);
          const next = index < 0 ? (event.shiftKey ? elements.length - 1 : 0) :
            (index + elements.length + (event.shiftKey ? -1 : 1)) % elements.length;
          elements[next].focus();
        }
      }
    }, true);
  }

  const drawer = document.getElementById("__drawer");
  if (drawer && primary) {
    const trigger = document.querySelector(".md-header__button[data-guide-toggle='__drawer']");
    const mobile = window.matchMedia("(max-width: 76.234375em)");
    const originalRole = primary.getAttribute("role");
    const originalLabel = primary.getAttribute("aria-label");
    const close = document.createElement("button");
    close.type = "button";
    close.className = "guide-drawer-close md-icon";
    close.setAttribute("aria-label", words.closeNavigation);
    close.textContent = "×";
    close.addEventListener("click", () => drawer.click());
    primary.appendChild(close);
    const focusable = () => [...primary.querySelectorAll("a[href], button, [tabindex='0']")].filter(element => {
      const rect = element.getBoundingClientRect();
      return rect.width && rect.height && rect.right > 0 && rect.left < window.innerWidth && getComputedStyle(element).visibility === "visible";
    });
    const updateDrawer = () => {
      if (drawer.checked && mobile.matches) {
        primary.setAttribute("role", "dialog");
        primary.setAttribute("aria-modal", "true");
        primary.setAttribute("aria-label", words.menu);
        requestAnimationFrame(() => close.focus());
      } else {
        if (originalRole) primary.setAttribute("role", originalRole);
        else primary.removeAttribute("role");
        primary.removeAttribute("aria-modal");
        if (originalLabel) primary.setAttribute("aria-label", originalLabel);
        else primary.removeAttribute("aria-label");
        if (mobile.matches && primary.contains(document.activeElement)) trigger?.focus();
      }
    };
    drawer.addEventListener("change", updateDrawer);
    mobile.addEventListener("change", updateDrawer);
    document.addEventListener("keydown", event => {
      if (!drawer.checked || !mobile.matches) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        drawer.click();
        trigger?.focus();
      } else if (event.key === "Tab") {
        const elements = focusable();
        const first = elements[0], last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }
    }, true);
  }

  function enhanceContent() {
    // Copy controls are not navigation landmarks; their buttons remain exposed.
    document.querySelectorAll(".md-code__nav").forEach(nav => nav.setAttribute("role", "presentation"));
    document.querySelectorAll(".md-typeset__scrollwrap, .md-typeset pre > code").forEach((region, index) => {
      const overflowing = region.clientWidth > 0 && region.scrollWidth > region.clientWidth + 1;
      if (overflowing) {
        region.tabIndex = 0;
        region.setAttribute("role", "region");
        region.setAttribute("aria-label", `${region.tagName === "CODE" ? words.code : words.table} ${index + 1}: ${words.scroll}`);
        region.dataset.guideScroll = "";
      } else if (region.hasAttribute("data-guide-scroll")) {
        region.removeAttribute("tabindex");
        region.removeAttribute("role");
        region.removeAttribute("aria-label");
        delete region.dataset.guideScroll;
      }
    });
  }
  window.addEventListener("resize", enhanceContent);
  document.addEventListener("toggle", enhanceContent, true);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhanceContent);
  else enhanceContent();
  requestAnimationFrame(enhanceContent);
})();
