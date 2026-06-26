import { search, recordAction } from "./registry.js";

const $ = (sel) => document.querySelector(sel);
let isOpen = false;
let activeIndex = -1;
let currentItems = []; // flat list of currently rendered items to allow up/down nav

export function initPaletteUI() {
  const overlay = $("#cmd-palette-overlay");
  const input = $("#cmd-search-input");
  const resultsContainer = $("#cmd-results");

  function open() {
    isOpen = true;
    overlay.classList.add("open");
    input.value = "";
    renderResults("");
    // small timeout to allow display block transition
    setTimeout(() => input.focus(), 10);
  }

  function close() {
    isOpen = false;
    overlay.classList.remove("open");
    input.blur();
  }

  function toggle() {
    isOpen ? close() : open();
  }

  function executeItem(index) {
    if (index >= 0 && index < currentItems.length) {
      const item = currentItems[index];
      recordAction(item);
      close();
      if (typeof item.action === "function") {
        item.action();
      }
    }
  }

  function renderResults(query) {
    const groups = search(query);
    resultsContainer.innerHTML = "";
    currentItems = [];
    activeIndex = 0; // select first by default

    if (groups.length === 0) {
      resultsContainer.innerHTML = `<div class="cmd-empty">No matching commands found.</div>`;
      return;
    }

    groups.forEach((group) => {
      const gEl = document.createElement("div");
      gEl.className = "cmd-group";
      gEl.innerHTML = `<div class="cmd-group-title">${group.category}</div>`;
      
      group.items.forEach((item) => {
        const iEl = document.createElement("div");
        iEl.className = "cmd-item";
        iEl.innerHTML = `
          <span class="cmd-item-title">${item.title}</span>
          <span class="cmd-item-prov">${item.provider}</span>
        `;
        
        const currentIndex = currentItems.length;
        currentItems.push(item);
        
        if (currentIndex === activeIndex) {
          iEl.classList.add("active");
        }

        iEl.addEventListener("mouseenter", () => {
          updateActive(currentIndex);
        });

        iEl.addEventListener("click", () => {
          executeItem(currentIndex);
        });

        gEl.appendChild(iEl);
      });
      
      resultsContainer.appendChild(gEl);
    });
    
    // ensure active is visible
    scrollToActive();
  }

  function updateActive(newIndex) {
    if (newIndex < 0) newIndex = currentItems.length - 1;
    if (newIndex >= currentItems.length) newIndex = 0;
    
    activeIndex = newIndex;
    const itemEls = resultsContainer.querySelectorAll(".cmd-item");
    itemEls.forEach((el, idx) => {
      el.classList.toggle("active", idx === activeIndex);
    });
    scrollToActive();
  }

  function scrollToActive() {
    const activeEl = resultsContainer.querySelector(".cmd-item.active");
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest" });
    }
  }

  // Keyboard bindings
  window.addEventListener("keydown", (e) => {
    const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k";
    const isCmdP = (e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "p";
    
    if (isCmdK || isCmdP) {
      e.preventDefault();
      toggle();
      return;
    }

    if (isOpen) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        updateActive(activeIndex + 1);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        updateActive(activeIndex - 1);
      } else if (e.key === "Enter") {
        e.preventDefault();
        executeItem(activeIndex);
      }
    }
  });
  
  // Close when clicking overlay backdrop
  overlay.addEventListener("mousedown", (e) => {
    if (e.target === overlay) {
      close();
    }
  });

  input.addEventListener("input", (e) => {
    renderResults(e.target.value);
  });
}
