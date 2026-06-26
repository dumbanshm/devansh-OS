// Simple spatial navigation for arrow keys.

function getFocusables() {
  return Array.from(document.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )).filter((el) => {
    // Must be visible
    const rect = el.getBoundingClientRect();
    return !el.disabled && rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  });
}

function getCenter(rect) {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

function distance(c1, c2) {
  return Math.sqrt(Math.pow(c1.x - c2.x, 2) + Math.pow(c1.y - c2.y, 2));
}

function handleArrow(e) {
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
    // If the active element is an input and we are typing, don't steal focus unless it's a specific case.
    if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
       // Let native input navigation work (unless we are at the edge, but for simplicity, ignore for inputs)
       return;
    }

    e.preventDefault();
    const focusables = getFocusables();
    if (!focusables.length) return;

    let active = document.activeElement;
    if (!active || !focusables.includes(active)) {
      focusables[0].focus();
      return;
    }

    const activeRect = active.getBoundingClientRect();
    const activeCenter = getCenter(activeRect);

    let bestMatch = null;
    let minDistance = Infinity;

    focusables.forEach((target) => {
      if (target === active) return;
      const targetRect = target.getBoundingClientRect();
      const targetCenter = getCenter(targetRect);

      let isValidDir = false;
      switch (e.key) {
        case "ArrowUp":
          isValidDir = targetCenter.y < activeCenter.y;
          break;
        case "ArrowDown":
          isValidDir = targetCenter.y > activeCenter.y;
          break;
        case "ArrowLeft":
          isValidDir = targetCenter.x < activeCenter.x;
          break;
        case "ArrowRight":
          isValidDir = targetCenter.x > activeCenter.x;
          break;
      }

      if (isValidDir) {
        // Bias distance calculation to strongly prefer things directly in the line of sight
        let dist = 0;
        if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            const dx = Math.abs(targetCenter.x - activeCenter.x);
            const dy = Math.abs(targetCenter.y - activeCenter.y);
            dist = dy + dx * 3; // heavily penalize x-distance
        } else {
            const dx = Math.abs(targetCenter.x - activeCenter.x);
            const dy = Math.abs(targetCenter.y - activeCenter.y);
            dist = dx + dy * 3; // heavily penalize y-distance
        }
        
        if (dist < minDistance) {
          minDistance = dist;
          bestMatch = target;
        }
      }
    });

    if (bestMatch) {
      bestMatch.focus();
    }
  }
}

export function initSpatialNav() {
  window.addEventListener("keydown", handleArrow);
  
  // Enter/Space mapping is native for buttons, but we can ensure it globally if needed.
  // Actually buttons naturally respond to space/enter.
  
  // Escape to close things is handled individually by overlays (e.g. detail.js, settings.js),
  // but we can add a generic escape blur.
  window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
          e.preventDefault(); // Prevent macOS from exiting fullscreen
          if (document.activeElement && document.activeElement !== document.body) {
              document.activeElement.blur();
          }
      }
  });
}
