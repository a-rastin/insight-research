# UI Context

## Theme

INSIGHT uses a **light, bright clinical workspace** designed for psychiatrists working with dense, safety-sensitive information. The primary canvas is white, surfaces are layered with very light neutral grays, and Carbon Teal (`--accent-primary`) is the only persistent accent in application chrome. The intended atmosphere is organized, modern, trustworthy, calm, and warm—not playful, decorative, or visually noisy.

The product brand shown to users is **INSIGHT**. The `Carbon Health` name present in the supplied design reference is treated only as the name of that reference design language and must not replace INSIGHT branding, copy, or logo.

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

## Colors

Define the palette once as CSS custom properties. Components must consume these variables; do not hardcode hex values in component styles, inline styles, Tailwind arbitrary values, SVGs, charts, or JavaScript state mappings.

```css
:root {
  --bg-base: #FFFFFF;
  --bg-surface: #F9FAFB;
  --bg-surface-subtle: #F3F4F6;

  --text-primary: #111827;
  --text-muted: #6B7280;
  --text-subtle: #9CA3AF;
  --text-on-accent: #FFFFFF;

  --accent-primary: #0A9E8F;
  --accent-primary-hover: #088A7D;
  --accent-primary-soft: #E6F6F5;

  --border-default: #E5E7EB;
  --border-strong: #D1D5DB;

  --state-error: #DC2626;
  --state-error-bg: #FEF2F2;
  --state-warning: #D97706;
  --state-warning-bg: #FFFBEB;
  --state-success: #059669;
  --state-success-bg: #ECFDF5;
  --state-follow-up: #7C3AED;
  --state-follow-up-bg: #F5F3FF;
  --state-info: #0284C7;
  --state-info-bg: #F0F9FF;
}
```

| Role | CSS Variable | Value |
| --- | --- | --- |
| Page background | `--bg-base` | `#FFFFFF` |
| Primary surface | `--bg-surface` | `#F9FAFB` |
| Secondary / hover surface | `--bg-surface-subtle` | `#F3F4F6` |
| Primary text | `--text-primary` | `#111827` |
| Muted text | `--text-muted` | `#6B7280` |
| Placeholder / disabled text | `--text-subtle` | `#9CA3AF` |
| Text on primary accent | `--text-on-accent` | `#FFFFFF` |
| Primary accent | `--accent-primary` | `#0A9E8F` |
| Primary accent hover | `--accent-primary-hover` | `#088A7D` |
| Selected / soft accent surface | `--accent-primary-soft` | `#E6F6F5` |
| Default border | `--border-default` | `#E5E7EB` |
| Strong border | `--border-strong` | `#D1D5DB` |
| Error / urgent | `--state-error` | `#DC2626` |
| Error / urgent tint | `--state-error-bg` | `#FEF2F2` |
| Warning | `--state-warning` | `#D97706` |
| Warning tint | `--state-warning-bg` | `#FFFBEB` |
| Success / normal | `--state-success` | `#059669` |
| Success / normal tint | `--state-success-bg` | `#ECFDF5` |
| Follow-up | `--state-follow-up` | `#7C3AED` |
| Follow-up tint | `--state-follow-up-bg` | `#F5F3FF` |
| Informational | `--state-info` | `#0284C7` |
| Informational tint | `--state-info-bg` | `#F0F9FF` |

### Color semantics

- `--state-error` represents urgent, critical, destructive, or validation-error states.
- `--state-warning` represents pending review, follow-up needed, caution, and non-blocking safety concerns.
- `--state-success` represents normal, complete, confirmed, or within-range states.
- `--state-follow-up` represents scheduled follow-up and chronic-care flags.
- `--state-info` represents neutral notices and contextual guidance.
- Every state must include a text label and an icon or other non-color cue.
- The Mermaid and PNG Bayesian-network diagrams in the archive use their own diagram colors. Those colors are model-documentation artifacts and are not application UI tokens.

## Typography

```css
:root {
  --font-display: "Neue Haas Grotesk Display", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-sans: "Neue Haas Grotesk Text", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", Menlo, Consolas, monospace;
}
```

| Role | Font | Variable | Size / metrics | Use |
| --- | --- | --- | --- | --- |
| Display / page heading | Neue Haas Grotesk Display, Inter fallback | `--font-display` | `32px`, `600`, `1.2`, `-0.02em` | Workspace title, major section title, empty state |
| UI body | Neue Haas Grotesk Text, Inter fallback | `--font-sans` | `15px`, `400`, `1.65`, `-0.005em` | Forms, clinical summaries, instructions, navigation |
| Label / caption | Same sans stack | `--font-sans` | `12px`, `500`, `1.4`, `0.02em` | Field labels, table headers, status labels, metadata |
| Clinical numeric / code | JetBrains Mono, Menlo fallback | `--font-mono` | `13px`, `400`, `1.6` | Patient codes, PANSS item codes and scores, dosages, vitals, timestamps, aligned numeric data |

Use a 20–32px range for section and page headings while preserving the display family and weight. The archive contains no font assets; these are font stacks, so Inter/system fallbacks must remain functional unless the preferred fonts are supplied separately.

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

| Context | Class / token |
| --- | --- |
| Inline / small UI | `rounded-[4px]` / `var(--radius-sm)` |
| Inputs and standard controls | `rounded-[8px]` / `var(--radius-md)` |
| Cards / panels | `rounded-[12px]` / `var(--radius-lg)` |
| Modals / overlays | `rounded-[16px]` / `var(--radius-xl)` |
| Pills / status badges / selectable slots | `rounded-full` / `var(--radius-pill)` |

Use the radius scale consistently. Do not introduce module-specific arbitrary radii unless a documented component requirement cannot be met by this scale.

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

## Spacing, Elevation, and Motion

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

  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-elevated: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-overlay: 0 20px 60px rgba(0, 0, 0, 0.12);

  --motion-fast: 100ms;
  --motion-base: 180ms;
  --motion-slow: 300ms;
  --motion-easing: cubic-bezier(0.4, 0, 0.2, 1);
  --motion-decelerate: cubic-bezier(0, 0, 0.2, 1);
}
```

- Build spacing on the 8px base. Reserve 4px for micro-gaps such as icon-to-label spacing and badge internals.
- Use card elevation for hoverable cards, elevated shadow for floating panels, and overlay shadow for dialogs.
- Use `100ms` for immediate selection feedback, `180ms` for ordinary state changes, and `300ms` for deliberate expansion/collapse.
- Alerts may enter from the top; non-urgent alerts persist for 4 seconds, while urgent alerts remain until dismissed.
- Honor `prefers-reduced-motion`. Replace movement with immediate state changes and replace animated skeletons with static loading text.

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

## Source Constraints and Open Decisions

1. **Dark mode:** required at product-prompt level but not specified by the design system. Dark tokens and contrast validation are still required.
2. **Right AI rail:** required by the product prompt; width, collapsed state, and breakpoint are unspecified.
3. **Icon library:** no package is selected.
4. **Preferred fonts:** font stacks are specified, but no font files are supplied.
5. **Component standardization:** modules currently span vanilla CSS, Tailwind CDN, and React/Vite. No shared component package is present.
6. **Branding:** user-facing branding is INSIGHT; do not expose the design-reference name as the product name.

## Source Coverage

This context was synthesized after inspecting all 97 files in the supplied archive. The archive contains 80 distinct payloads after exact-hash deduplication; 33 paths belong to duplicate groups. All 14 XML files parsed successfully, all 17 `.net` files were structurally scanned, all 8 Mermaid diagrams were inspected, and the PNG Bayesian-network diagram was reviewed. The clinical network files and guideline texts inform workflow and safety semantics but do not define application theme tokens. UI decisions above come from the global design contract, product prompts, architecture/context documents, and module README/handoff contracts.
