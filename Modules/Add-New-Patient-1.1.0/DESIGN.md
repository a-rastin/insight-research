---
version: alpha
name: Carbon Health
description: "A modern healthcare SaaS built on a white clinical canvas with Carbon Teal (#0A9E8F) as a trust-anchoring accent. Patient-facing UI reduces cognitive load through radical white space, deliberate status color semantics, and warm-but-precise typography — because healthcare anxiety deserves interfaces that calm, not confuse."

colors:
  primary: "#0A9E8F"
  primary-hover: "#088A7D"
  primary-light: "#E6F6F5"
  on-primary: "#FFFFFF"
  ink: "#111827"
  ink-muted: "#6B7280"
  ink-subtle: "#9CA3AF"
  canvas: "#FFFFFF"
  surface-1: "#F9FAFB"
  surface-2: "#F3F4F6"
  border: "#E5E7EB"
  border-strong: "#D1D5DB"
  urgent: "#DC2626"
  urgent-bg: "#FEF2F2"
  warning: "#D97706"
  warning-bg: "#FFFBEB"
  normal: "#059669"
  normal-bg: "#ECFDF5"
  follow-up: "#7C3AED"
  follow-up-bg: "#F5F3FF"
  info: "#0284C7"
  info-bg: "#F0F9FF"

typography:
  display:
    fontFamily: "Neue Haas Grotesk Display, Inter, -apple-system, sans-serif"
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: -0.02em
  body:
    fontFamily: "Neue Haas Grotesk Text, Inter, -apple-system, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: -0.005em
  label:
    fontFamily: "Neue Haas Grotesk Text, Inter, -apple-system, sans-serif"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0.02em
  mono:
    fontFamily: "JetBrains Mono, Menlo, monospace"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.6

spacing:
  base: 8px
  scale: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96]

radius:
  sm: 4px
  md: 8px
  lg: 12px
  xl: 16px
  pill: 9999px

shadows:
  card: "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)"
  elevated: "0 4px 12px rgba(0,0,0,0.08)"
  overlay: "0 20px 60px rgba(0,0,0,0.12)"

motion:
  duration-fast: 100ms
  duration-base: 180ms
  duration-slow: 300ms
  easing: cubic-bezier(0.4, 0, 0.2, 1)
  easing-decelerate: cubic-bezier(0, 0, 0.2, 1)
---

## Rationale

**Teal as clinical trust, not corporate cool** — Carbon Health's teal (#0A9E8F) sits at the intersection of medical authority and modern tech warmth. Pure blue reads as "insurance company"; green reads as "wellness app." Teal occupies a deliberate middle ground: it has the cleanliness of a clinical environment and the human warmth that differentiates Carbon from legacy EHR systems. It is used sparingly — primary actions, selected states, and key health metrics — precisely because healthcare patients respond to restraint as a signal of competence.

**White space as a clinical instrument** — Patients using healthcare apps are often anxious. Cluttered interfaces increase cortisol; white space communicates that the system is under control. Carbon's UI treats negative space as an active ingredient — large padding around cards, generous line height in body text, breathing room in appointment slots. The interface says: there is no emergency, we have time, everything is organized.

**A five-state status system that is never ambiguous** — Healthcare UI carries real-world consequences when status colors are misread. Carbon's status palette assigns distinct, semantically distinct hues to each clinical state: urgent (red), warning (amber), normal (green), follow-up (violet), informational (sky). No two states share a hue family. Each state also has a paired background tint so that status can be conveyed in both full-color and muted badge forms without losing meaning — critical for color-blind accessibility.

**Typography legibility as a patient safety feature** — Neue Haas Grotesk's large x-height and open counters make it readable at clinical densities — lab result tables, medication lists, appointment histories. The type system uses a separate monospaced scale for numeric health data (lab values, vitals, dosages) to ensure column alignment and to visually separate machine-generated data from human-authored notes. This distinction is a clinical convention that Carbon's digital design respects.

## 1. Visual Theme & Atmosphere
Carbon Health occupies the narrow lane between clinical authority and consumer approachability. The canvas is bright white — the same white as a clean examination room — with Carbon Teal (#0A9E8F) providing the only meaningful color in the UI chrome. Product photography and illustration use soft, desaturated palettes to avoid overstimulating anxious patients. The overall impression is: organized, modern, trustworthy, and warm — not cold, not playful.

The administrative dashboard (used by clinicians and staff) is denser: appointment grids, queue management, patient search. Here, the white canvas is preserved but information density increases — smaller type, tighter row heights, more visible grid lines. The patient-facing mobile interface is airier with larger touch targets and more prominent health status summaries.

## 2. Color System
**Canvas and structure**:
- White (#FFFFFF): primary canvas across all product surfaces
- Surface-1 (#F9FAFB): inset sections, sidebar backgrounds, table row backgrounds
- Surface-2 (#F3F4F6): hover states, selected row highlights
- Border (#E5E7EB): default dividers, card outlines

**Brand accent**:
- Carbon Teal (#0A9E8F): primary CTA, active nav, selected input borders, health metric highlights
- Teal light (#E6F6F5): teal-tinted backgrounds for selected states, tag fills
- Teal hover (#088A7D): pressed/hover interactive state

**Clinical status palette** (always paired: foreground + background tint):
- Urgent: #DC2626 / #FEF2F2 — active critical lab flags, emergency alerts
- Warning: #D97706 / #FFFBEB — follow-up needed, results pending review
- Normal: #059669 / #ECFDF5 — results within range, appointment confirmed
- Follow-up: #7C3AED / #F5F3FF — scheduled follow-up, chronic care flags
- Info: #0284C7 / #F0F9FF — informational notices, appointment reminders

Status colors never appear as large background fills — only as foreground text, icon fills, and left-border accent stripes on cards. This prevents any surface from feeling alarming at a glance.

## 3. Typography
**Neue Haas Grotesk** (Inter as fallback) is the rational choice for a healthcare platform: large x-height for legibility under stress, open apertures that remain distinct at small sizes, and a neutral voice that doesn't compete with clinical content for attention.

- **Display/Headings**: Neue Haas Grotesk Display, 600 weight, -0.02em tracking, 32–20px scale for section headers and empty-state messaging
- **Body**: Neue Haas Grotesk Text, 400 weight, 15px, 1.65 line height — optimized for reading health summaries and instructions
- **Labels/Captions**: 12px, 500 weight, +0.02em tracking — form field labels, table column headers, status badge text
- **Monospace**: JetBrains Mono for lab values, vital sign readings, prescription dosages, and any numeric health data that requires alignment

Type color uses the full ink scale: #111827 for primary content, #6B7280 for secondary/supporting, #9CA3AF for placeholder and disabled states.

## 4. Components & Patterns
**Appointment card**: Date + time block (left) + provider avatar + type badge + status pill. Status pill uses the clinical palette's paired color scheme. Hover state lifts card with shadow elevation.

**Lab result row**: Test name + value + unit + reference range + status flag. Numeric values are monospaced and right-aligned. Out-of-range values display the urgent or warning color on the value itself — not the row background.

**Health record card**: Section header with category icon (in teal), collapsed by default, expand chevron. Content uses generous padding (24px) to separate record fields visually.

**Vital signs grid**: 2×3 card grid of current vitals (HR, BP, SpO2, temp, weight, BMI). Each cell has the metric name, current value (large mono), trend arrow, and comparison to last visit. Abnormal vitals use the status color on the value only.

**Medication list item**: Drug name (bold) + dose + frequency + prescriber. Refill-needed state uses the warning amber as a left-border stripe.

**Appointment scheduling flow**: Three-step modal (date → time → confirmation) with a teal progress indicator. Time slots are a grid of pills — available in teal-light, selected in teal, unavailable in surface-2.

**Message thread (patient-provider messaging)**: Left-anchored provider bubbles (surface-1 background, ink text), right-anchored patient bubbles (teal background, white text). Timestamp in ink-subtle below.

## 5. Spacing & Layout
**Patient-facing mobile**: 16px horizontal margin, 20px card padding, 48px touch targets minimum. Section separation uses 24px vertical gap. Lists use 16px row padding.

**Clinical dashboard (desktop)**: 256px left sidebar (navigation + quick stats), main content at max 1200px. Appointment grid: 15-minute slots at 40px row height. Patient list: 48px row height with 16px horizontal padding. Top header: 56px fixed.

**Cards and surfaces**: 16px padding for compact cards (appointment items), 24px for content cards (health records), 32px for primary action cards (new appointment, new message).

The spacing system is built on an 8px base. The 4px unit is used only for internal micro-gaps (icon-to-label spacing, badge internal padding). All interactive targets are padded to a minimum of 44×44px.

## 6. Motion & Interaction
**Status transitions**: When a lab result status changes (e.g., pending → flagged), the status pill transitions color over 180ms with a subtle fade — not an abrupt swap. This prevents jarring visual changes in high-stress contexts.

**Card expansion**: Health record sections expand with a 300ms ease-decelerate — slower than typical UI to feel deliberate and controlled, matching the paced, careful communication cadence of clinical information.

**Scheduling interaction**: Time slot selection uses an immediate fill (100ms) to give confident tactile feedback. The confirmation step animates in from the right (horizontal slide, 180ms) to reinforce the linear booking flow.

**Loading states**: Skeleton loaders on appointment cards and lab result rows — not spinners. Skeleton shapes match the content they represent so the visual structure is never lost during load.

**Notifications/alerts**: Status alerts slide in from the top with a 200ms ease-out, persist for 4 seconds, and fade out over 300ms. Urgent alerts (red) persist until manually dismissed.

All animations respect `prefers-reduced-motion` — transitions collapse to immediate with no movement.

## Accessibility

### Contrast Ratios
- **Teal on white** (#0A9E8F on #FFFFFF): 3.6:1 — passes AA for large text and UI components, fails for small body text (use ink for body text only)
- **White on Teal** (#FFFFFF on #0A9E8F): 3.6:1 — passes AA for large text, UI buttons at 16px+; use only for bold/large text contexts
- **Primary ink on white** (#111827 on #FFFFFF): 17.9:1 — passes AA and AAA
- **Muted ink on white** (#6B7280 on #FFFFFF): 4.7:1 — passes AA, fails AAA
- **Urgent red on white** (#DC2626 on #FFFFFF): 4.5:1 — passes AA exactly
- **Urgent red on urgent-bg** (#DC2626 on #FEF2F2): 4.2:1 — passes AA for large text/bold labels
- **Normal green on white** (#059669 on #FFFFFF): 3.0:1 — passes AA only for UI components (icons, borders); pair with text label for status conveyed at small sizes

### Minimum Requirements
- **Touch target**: 44×44px minimum on all mobile interactive elements; 36×36px minimum on desktop with pointer
- **Focus indicator**: 2px solid #0A9E8F outline, 2px offset — ensures teal brand color doubles as focus ring on white canvas
- **Focus contrast**: Teal focus ring on white achieves 3.6:1 (meets non-text contrast requirement of 3:1 per WCAG 2.1 §1.4.11)
- **Color independence**: Every status state (urgent/warning/normal/follow-up/info) pairs a color with an icon (⚠ ✓ ↩ ℹ) and text label — status is never communicated by color alone

### Motion
- All transitions respect `prefers-reduced-motion: reduce` — animations suppressed, transitions replaced with instant state changes
- Skeleton loaders are suppressed under reduced-motion; a static "Loading…" text label replaces them
- The appointment scheduling slide-in collapses to an immediate render under reduced-motion

### Notes
- Carbon Teal (#0A9E8F) at 3.6:1 is not sufficient for small body text on white — restrict teal foreground use to headings (18px+), bold labels, and button text (where 3:1 UI component threshold applies)
- The five-status clinical color system is designed to be partially color-blind safe: the urgent/normal pair (red/green) is supplemented with icons and labels, preventing deuteranopia confusion
- All lab result values rendered in monospace should also include accessible `aria-label` attributes that spell out the unit and reference range for screen reader users
- Patient health data tables must use `scope="col"` and `scope="row"` header associations — not just visual formatting — to remain usable with assistive technology
