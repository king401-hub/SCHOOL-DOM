// What a teacher sees while their workspace loads (or if it can't): a quiet
// skeleton of the real layout instead of a spinner on a blank page.
import { AlertTriangle } from "lucide-react";
import { Skeleton } from "./TeacherKit";

export function TeacherLoading({ message = "Getting your classroom ready…" }) {
  return (
    <div className="teacher-workspace-shell ts ts-loading" role="status" aria-live="polite" aria-busy="true">
      <aside className="ts-sidebar ts-loading__side" aria-hidden="true">
        <div className="ts-loading__brand">
          <Skeleton width={38} height={38} radius={12} />
          <div>
            <Skeleton width={120} height={12} />
            <Skeleton width={78} height={9} style={{ marginTop: 8 }} />
          </div>
        </div>
        <Skeleton width="100%" height={40} radius={13} />
        <div className="ts-loading__nav">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((row) => (
            <Skeleton key={row} width={row % 3 === 0 ? "78%" : "92%"} height={30} radius={11} />
          ))}
        </div>
      </aside>

      <div className="ts-main">
        <header className="ts-topbar" aria-hidden="true">
          <Skeleton width={150} height={14} />
          <span className="ts-topbar__spacer" />
          <Skeleton width={160} height={40} radius={13} />
          <Skeleton width={40} height={40} radius={13} />
        </header>
        <div className="ts-content ts-loading__main">
          <p className="ts-loading__message">{message}</p>
          <Skeleton className="ts-loading__hero" width="100%" height={210} radius={28} />
          <div className="ts-loading__tiles" aria-hidden="true">
            {[0, 1, 2, 3].map((tile) => (
              <Skeleton key={tile} width="100%" height={112} radius={20} />
            ))}
          </div>
          <div className="ts-loading__cols" aria-hidden="true">
            <Skeleton width="100%" height={260} radius={20} />
            <Skeleton width="100%" height={260} radius={20} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function TeacherLoadError({ message, onRetry }) {
  return (
    <div className="ts-loaderror" role="alert">
      <span className="ts-loaderror__icon" aria-hidden="true"><AlertTriangle size={26} /></span>
      <h2>We couldn't open your workspace</h2>
      <p>{message || "Something went wrong while loading your dashboard."}</p>
      {onRetry ? (
        <button type="button" className="ts-loaderror__btn" onClick={onRetry}>Try again</button>
      ) : null}
    </div>
  );
}
