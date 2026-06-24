// Per-metric muted color ramps. Single source of truth for heatmap intensity,
// card accents and timeline dots. Dark-first, desaturated — no bright colors.
// Each ramp: index 0 = empty/idle cell, 1..4 = increasing intensity.

export const RAMPS = {
  green:  ["#16201b", "#1e3a2a", "#2f6b41", "#3f9a5a", "#56c878"], // coding
  amber:  ["#211c12", "#3a2f15", "#6b5320", "#9a7a2c", "#d0a83e"], // dsa
  violet: ["#1c1726", "#2c2340", "#473366", "#6a4d9a", "#9277cf"], // gym
  blue:   ["#121a26", "#1a2c44", "#234a72", "#2f6aa6", "#4391d6"], // sleep
  teal:   ["#101f1f", "#163838", "#1f5e5e", "#2a8787", "#3bb3b3"], // deep work
  rose:   ["#241318", "#3e1c25", "#6b2c3a", "#9a3d52", "#cf5772"], // chemvecto
  indigo: ["#15162a", "#21244a", "#333a78", "#4b54a8", "#6b76d0"], // claude
  orange: ["#231a12", "#3a2a14", "#6b4a1e", "#9a6c2c", "#d09340"], // protein
  slate:  ["#181b21", "#262b34", "#3a4150", "#525c6e", "#6f7a8c"], // fallback
};

// Accent (text/border) per color — the brightest ramp step.
export function accent(color) {
  const r = RAMPS[color] || RAMPS.slate;
  return r[r.length - 1];
}

// Map a value to a ramp index (0..4).
// - count metrics: 0,1,2,3,4+ buckets.
// - scaled metrics (sleep/deep work): value/scaleMax across 4 bands.
export function rampIndex(value, scaleMax) {
  if (!value || value <= 0) return 0;
  if (scaleMax) {
    const frac = Math.min(value / scaleMax, 1);
    return Math.min(4, Math.max(1, Math.ceil(frac * 4)));
  }
  if (value >= 4) return 4;
  return Math.max(1, Math.round(value));
}

export function cellColor(color, value, scaleMax, binary) {
  const ramp = RAMPS[color] || RAMPS.slate;
  // Binary metrics (e.g. workout done): dark for 0, full color for 1+.
  if (binary) return ramp[value > 0 ? 4 : 0];
  return ramp[rampIndex(value, scaleMax)];
}
