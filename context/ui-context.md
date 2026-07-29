# UI Context

## Product Identity and Branding

The product name is **INSIGHT**.

Use `INSIGHT` for the principal product wordmark. Product-logo treatments should use the uppercase form.

## Current Design Character

INSIGHT is a desktop-first clinical decision-support workspace for psychiatrists. Its dominant visual language is:

- bright and predominantly light;
- white or near-white clinical surfaces;
- dark neutral text;
- restrained teal for primary actions and selection;
- explicit semantic colors for urgent, warning, normal, follow-up, and informational states;
- compact, information-dense clinical workspaces;
- wider spacing on authentication and initial-entry states;
- clear clinician review, provenance, and safety messaging;
- minimal decorative imagery.

The visual tone should be organized, calm, serious, and modern. Avoid playful illustration, decorative gradients, glassmorphism, excessive blur, neon colors, oversized marketing typography inside clinical workspaces, or consumer-wellness styling.

## Theme

Use color sparingly:

- Teal is reserved for primary actions, active navigation, selected controls, focus indicators, and selected clinical metrics.
- Clinical state colors are restricted to text, icons, badges, borders, and narrow accent stripes. Do not use them as large page or card fills.
- Primary body copy always uses the ink tokens, not teal.
- Clinical dashboards may be information-dense; patient-facing surfaces, if added, must use more whitespace and larger touch targets.

### Theme-mode status

The supplied product prompt requests a dark/light mode toggle, but the archive defines only a light palette and provides no dark tokens, contrast validation, or dark-theme component contract. Therefore:

- The light theme below is the only approved theme in the current context.
- Do not derive dark colors by inversion and do not invent dark tokens.
- Do not expose a functional dark-mode toggle until an approved dark palette and accessibility review are supplied.
- Treat dark mode as an unresolved product/design decision, not as implemented behavior.

## Canonical Color System

The canonical palette is the teal/neutral system used in the shared design references and implemented most directly by Dashboard, Diagnosis, Severity, and Suicide Risk.

Use repository-aligned token names:

```css
:root {
  --primary: #0A9E8F;
  --primary-hover: #088A7D;
  --primary-light: #E6F6F5;
  --on-primary: #FFFFFF;

  --ink: #111827;
  --ink-muted: #6B7280;
  --ink-subtle: #9CA3AF;

  --canvas: #FFFFFF;
  --surface-1: #F9FAFB;
  --surface-2: #F3F4F6;

  --border: #E5E7EB;
  --border-strong: #D1D5DB;

  --urgent: #DC2626;
  --urgent-bg: #FEF2F2;

  --warning: #D97706;
  --warning-bg: #FFFBEB;

  --normal: #059669;
  --normal-bg: #ECFDF5;

  --follow-up: #7C3AED;
  --follow-up-bg: #F5F3FF;

  --info: #0284C7;
  --info-bg: #F0F9FF;
}
```

### Color roles

| Role | Token | Use |
| --- | --- | --- |
| Main page and card background | `--canvas` | Primary reading surface |
| Sidebar, inset region, alternate panel | `--surface-1` | Low-emphasis structure |
| Hover, disabled, selected-neutral surface | `--surface-2` | Secondary state |
| Main text | `--ink` | Body copy, headings, values |
| Supporting text | `--ink-muted` | Instructions, metadata, helper text |
| Placeholder and low-emphasis text | `--ink-subtle` | Disabled and tertiary information |
| Primary action and selected state | `--primary` | CTA, selected navigation, focus, progress |
| Primary hover | `--primary-hover` | Pointer hover and pressed emphasis |
| Soft selected state | `--primary-light` | Selected pills, tags, metric accents |
| Critical state | `--urgent` / `--urgent-bg` | Urgent finding, destructive action, blocking error |
| Caution state | `--warning` / `--warning-bg` | Review required, stale or incomplete data |
| Normal state | `--normal` / `--normal-bg` | Complete, available, within range |
| Follow-up state | `--follow-up` / `--follow-up-bg` | Ongoing care or scheduled follow-up |
| Informational state | `--info` / `--info-bg` | Neutral guidance and provenance |

### Color usage rules

- Use teal for primary actions, active navigation, selected controls, progress, and focus indicators.
- Use `--ink` for normal body text. Do not use teal as general paragraph text.
- Pair every clinical state color with visible text and, where practical, an icon or shape.
- Prefer a state-colored border, icon, badge, or narrow left stripe over a large saturated fill.
- Light semantic background tints are acceptable for banners and safety cards when the state must remain continuously visible.
- Never use red and green as the only distinction between two clinical outcomes.

### Verified contrast constraint

`#0A9E8F` against white is approximately `3.33:1`. It is suitable for non-text UI boundaries and sufficiently large or bold text, but not for ordinary small body text. White on `#0A9E8F` has the same approximate contrast, so primary-button labels must be adequately sized and weighted. For small critical copy, use darker ink-compatible state colors or pair color with another cue.

## Existing Palette Deviations

Several modules currently use related but noncanonical green/teal palettes. These are existing implementation facts, not additional global themes.

| Module | Current primary/accent | Notable deviation |
| --- | --- | --- |
| Add New Patient | `#156C5B` | Green accent, blue focus ring, green/blue background gradient, large hero heading |
| Medical History | `#176B5B` | Arial typography, blue focus ring, rust-red secondary accent |
| DDI Checker | `#276A73` | Blue-green brand color and larger tinted severity-card backgrounds |
| Treatment Plan | `#087F74` / `#06665E` | Darker teal to improve action contrast |
| BN Manager | No teal brand token | Plain gray utility/status page |

When creating a new module, use the canonical palette rather than selecting one of these variants. When modifying an existing divergent module, avoid adding further colors; standardize only when the requested scope permits it.

## Typography

```css
:root {
  --font-sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace;
}
```

### Type roles

| Role | Size and weight | Use |
| --- | --- | --- |
| Major workspace title | `28–32px`, `600–700`, line-height `1.15–1.25` | Dashboard, risk assessment, major standalone workspace |
| Module/page title | `20–26px`, `600–700` | Diagnosis, Severity, Treatment Plan sections |
| Section title | `16–20px`, `600–700` | Cards, form sections, safety panels |
| Clinical body | `14–15px`, `400`, line-height `1.5–1.65` | Instructions, descriptions, findings |
| Label/caption | `11–13px`, `600–800` | Field labels, metadata, table headers, status kickers |
| Numeric/code data | `12–15px`, mono | Patient identifiers, scores, versions, dosages, timestamps |
| Large score/metric | `22–32px`, mono, `600–700` | PANSS totals, risk score, dashboard metrics |

Uppercase labels are used for compact metadata and section kickers. Keep tracking restrained; the implemented repository frequently uses uppercase labels without large letter spacing.

## Border Radius

```css
:root {
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-pill: 9999px;
}
```

Implementation guidance:

- Dense buttons and inputs may use `6px` where matching Dashboard, DDI Checker, Medical History, or Suicide Risk.
- Standard controls should normally use `8px`.
- Main clinical cards should use `8px` or `12px`.
- Major overlays may use `10–16px`.
- Status pills, score choices, and compact chips use pill radius.
- Do not introduce highly rounded consumer-app cards or mixed arbitrary radii within one surface.

## Spacing, Elevation, and Motion

### Spacing scale

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
}
```

Use an 8px base rhythm. Use 4px for internal micro-gaps, not for main page spacing.

Typical repository values:

- page padding: `16–28px` on dense workspaces;
- card padding: `14–24px`;
- primary form/card padding: `24–32px`;
- column gap: `18–24px`;
- mobile page padding: `10–16px`;
- section separation: `16–28px`.

### Shadows

```css
:root {
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-elevated: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-overlay: 0 20px 60px rgba(0, 0, 0, 0.12);
}
```

Use subtle borders as the primary surface separator. Shadows should remain restrained. Do not use large floating shadows on every card.

### Motion

```css
:root {
  --motion-fast: 100ms;
  --motion-base: 180ms;
  --motion-slow: 300ms;
  --motion-easing: cubic-bezier(0.4, 0, 0.2, 1);
  --motion-decelerate: cubic-bezier(0, 0, 0.2, 1);
}
```

- Use `100ms` for immediate selection feedback.
- Use `180ms` for hover, border, background, and ordinary state changes.
- Use `300ms` only for deliberate progress or expansion.
- Use content-shaped skeletons where the repository already does so.
- Honor `prefers-reduced-motion` by suppressing shimmer and movement.
- Urgent information must not disappear automatically.

- Use semantic HTML as the baseline contract.
- Reuse the module's existing framework rather than introducing a second UI runtime.
- Do not introduce a new cross-project component library as an incidental change.
- Keep browser URLs relative to the gateway.
- Scope CSS to the module root when embedding or when selector collision is possible.
- Treat embeddability as module-specific. Diagnosis explicitly supports an embedded root and suppresses standalone chrome; do not assume every module already has the same mount/unmount contract.

## Component Library

There is **no single project-wide component library** defined in the supplied archive. Do not claim or assume shadcn/ui, Material UI, Lucide, or another library as an existing dependency.

Current module implementations are heterogeneous:

- Dashboard, Add New Patient, Authentication, Diagnosis, and several lightweight modules use semantic HTML, plain CSS, and vanilla JavaScript.
- Severity uses a single HTML file with Tailwind loaded by CDN and vanilla JavaScript.
- Treatment Plan uses React with Vite for the psychiatrist review workspace.

The shared UI contract is therefore **token-first and framework-neutral**:

1. Put the global CSS custom properties in the host theme stylesheet.
2. Scope module selectors beneath the module mount root.
3. Use semantic HTML as the base component contract.
4. Add a React wrapper only inside modules already using React or when a separately approved migration establishes a shared React component package.
5. Do not introduce a new cross-project component library as an incidental change.
6. Embedded modules must expose mount/unmount behavior, render only inside their supplied root, and must not duplicate host navigation or top-bar chrome.

### Required reusable patterns

- **Primary button:** teal fill, teal-hover state, visible disabled state, and a 2px teal focus ring with 2px offset. White-on-teal labels must be sufficiently large/bold; do not use teal for small body text.
- **Secondary button:** white or neutral surface, ink text, default border, strong border on hover/focus.
- **Destructive / urgent action:** error token plus explicit text; never rely on red alone.
- **Form control:** persistent label, helper/error slot, strong visible focus state, and programmatic association between label, control, and error.
- **Status badge:** foreground state color plus light state tint, icon, and text label. Never use a state-colored full-card background.
- **Clinical card/panel:** neutral surface, default border, 12px radius, and 16px, 24px, or 32px padding according to content density.
- **Clinical table/list row:** explicit column headers, aligned monospaced numeric values, row-level actions, and semantic row/column header associations.
- **Criteria checklist:** grouped DSM criteria, checkbox controls, real-time server-derived evaluation text, a gated confirmation action, and a separately labeled clinician bypass action.
- **PANSS score selector:** item code/name/description, keyboard-operable 1–7 score buttons, textual severity label, and live totals/progress.
- **Sticky clinical summary:** patient context, progress, subscale/total scores, interpretation, and final actions; used by the Severity workspace.
- **Patient search/result row:** searchable patient fields, one patient per row, clear selection state, and no PHI in URLs.
- **Medication / DDI alert:** medication pair, severity, recommendation, evidence, and accepted/dismissed/overridden state. Override dialogs require a clinical rationale and must preserve validation errors visibly.
- **Treatment-plan review panel:** explainable recommendation, source/provenance context, editable structured fields, safety findings, psychiatrist modifications, and explicit finalization controls.
- **Wizard / stepper:** used for Add New Patient and Follow-up multi-step workflows. Preserve progress and show gated next actions without hiding clinician override paths that are explicitly allowed by the workflow.
- **Dialog / modal:** centered overlay using overlay elevation and `--radius-xl`; return focus to the invoking control when closed. Do not add backdrop blur unless separately specified.
- **Loading state:** content-shaped skeletons rather than indeterminate spinners. Under reduced motion, use static loading text.
- **Message thread / assistant panel:** provider/system messages on a neutral surface and psychiatrist messages on the accent surface, with timestamps in subtle text. The assistant is advisory and must not present controls that directly mutate clinical data.

## Layout Patterns

- **Application shell:** desktop-first clinical workspace. Use a fixed `56px` top header, a fixed `256px` left navigation sidebar, and a main content region capped at `1200px`.
- **Dashboard content:** show `Workspace`, current date/time, and the authenticated psychiatrist name as `Dr. …`. Psychiatrist navigation exposes Add New Patient, Patient Follow-up, List of Patients, and Setting. Admin navigation exposes Add New User, Logs, Backup, and List of Users.
- **Three-region dashboard target:** the product prompt also calls for a central brief-report area and a right-side AI assistant rail. Their exact width, collapse behavior, and responsive breakpoint are not specified in the archive; do not invent fixed dimensions. Dashboard remains a navigation/workspace shell and must not own downstream clinical logic.
- **Sidebar:** separate from content with `--border-default`; use `--bg-surface` for the sidebar background and the accent tokens only for the active item.
- **Top header:** fixed height, bottom border, workspace title, date/time, authenticated display name, and account/session actions. Embedded clinical modules must not render a second header.
- **Embedded module:** the host owns topbar, sidebar, return navigation, session state, and browser history. A module renders only within its mount root, supports clean teardown, and does not alter the host URL unless the host contract explicitly permits it.
- **Authentication:** standalone, simple, centered flow with INSIGHT name/logo. Support login, disclaimer, forced-password-change, loading, and error states without importing Dashboard chrome.
- **Multi-step intake:** Add New Patient uses Diagnosis → Patient Data → Disorder Severity → Treatment Options → Summary. Keep one primary task per step, show progress, and preserve entered data between steps.
- **Multi-step follow-up:** Find Patient → Patient Report → Disorder Severity → Treatment Options → Summary. Search/list precedes any patient-specific clinical workspace.
- **Diagnosis workspace:** grouped criteria tree with real-time interpretation and two clinician decision paths. When embedded, omit the standalone header and back-to-dashboard control.
- **Severity workspace:** on desktop, use a two-column layout: tabbed PANSS item grid on the left and a sticky context/score/interpretation/action column on the right. The exact responsive breakpoint is not specified.
- **Treatment-plan workspace:** React-based psychiatrist review surface; visually follow the same tokens even though its implementation framework differs from other modules.
- **Dense rows:** appointment-grid rows may use `40px` height; patient-list rows use `48px` height with `16px` horizontal padding.
- **Card spacing:** compact cards use `16px` padding, content cards `24px`, and primary-action cards `32px`.
- **Desktop interaction target:** minimum `36px × 36px` for pointer-driven controls.
- **Mobile / touch target:** minimum `44px × 44px`; the patient-facing design reference uses `48px` targets, `16px` horizontal page margins, `20px` card padding, and `24px` section gaps.
- **Data tables:** use real table semantics where the information is tabular; do not recreate clinical tables with visually aligned generic `<div>` elements.

## Icons

No canonical icon library is named in the supplied files. Do not declare an icon dependency without a separate implementation decision.

Until an icon system is selected:

- Use a single consistent SVG or native-symbol source within each surface; do not mix unrelated icon styles.
- Pair every clinical status icon with visible text.
- Use the documented semantic cues: warning/urgent `⚠`, normal/complete `✓`, follow-up `↩`, and information `ℹ`, or accessible SVG equivalents with the same meaning.
- Category icons may use `--accent-primary`; urgent/warning/success/follow-up/info icons use the corresponding state token.
- Decorative icons must be hidden from assistive technology. Interactive icon-only controls require an accessible name and tooltip.
- The archive does not specify exact icon glyph sizes. Size icons relative to their control and preserve the minimum control target dimensions rather than inventing a global pixel size.

## Accessibility and Clinical-Safety UI Rules

- Primary ink on white is the default reading combination.
- Teal on white is not suitable for small body text. Restrict teal foreground text to sufficiently large/bold labels, headings, and UI-component use.
- Use a `2px solid var(--accent-primary)` focus outline with `2px` offset on every interactive element.
- Do not communicate status, severity, completion, risk, or availability by color alone.
- Use semantic headings, landmarks, labels, fieldsets, legends, and tables.
- Clinical tables require `scope="col"` and `scope="row"` associations where applicable.
- Monospaced clinical values require accessible labels that spell out units and reference ranges when the visible compact notation is ambiguous.
- Disabled actions must explain the unmet prerequisite nearby; do not rely only on reduced opacity.
- Decision-support language must preserve psychiatrist authority. Use wording such as `Decision-support recommendation. Psychiatrist final review required.` Do not label recommendations as an app decision, AI prescription, or automatic diagnosis.
- The AI assistant is advisory, page-aware, and read-only with respect to application data. Never show patient names in assistant-bound content.
- Do not put patient names, patient codes, or other PHI into browser URLs, filenames, analytics labels, or error traces.


