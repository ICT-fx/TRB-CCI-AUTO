/**
 * Code-built brand mark recreating the TRB Chemedica logo structure
 * (circular emblem above a serif wordmark) — rendered as "ORB".
 * Pure SVG + text, no image asset.
 */
export function OrbLogo() {
  return (
    <div className="flex flex-col items-center gap-3">
      <svg
        viewBox="0 0 120 120"
        role="img"
        aria-label="ORB"
        className="h-28 w-28 sm:h-32 sm:w-32"
      >
        <circle cx="60" cy="60" r="52" fill="#ffffff" stroke="#15578f" strokeWidth="7" />
        <text
          x="60"
          y="60"
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily="var(--font-fraunces), Georgia, serif"
          fontSize="36"
          fontWeight="700"
          letterSpacing="-1.5"
          fill="#15578f"
        >
          ORB
        </text>
      </svg>
      <span className="font-display text-5xl font-semibold tracking-tight text-trb-blue-dark sm:text-6xl">
        ORB
      </span>
    </div>
  );
}
