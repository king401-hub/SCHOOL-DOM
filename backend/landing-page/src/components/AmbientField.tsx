/** Slow-drifting ambient gradient wash sitting behind the entire site (fixed,
 * z-index -1, pointer-events none) - the flat solid body background read as
 * lifeless, this gives every section some living motion instead of only the
 * hero having its own static wash. Pure CSS (no WebGL - there's already a
 * carefully budgeted 3D piece, this must not add a second GPU workload),
 * theme-aware via the existing --c-green-rgb/--c-ink-rgb tokens so it
 * inverts correctly in dark mode automatically, and stilled entirely under
 * prefers-reduced-motion (see .ambient-blob in index.css). */
export default function AmbientField() {
  return (
    <div className="ambient-field" aria-hidden="true">
      <span className="ambient-blob ambient-blob-1" />
      <span className="ambient-blob ambient-blob-2" />
      <span className="ambient-blob ambient-blob-3" />
    </div>
  );
}
