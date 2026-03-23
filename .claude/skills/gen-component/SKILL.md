---
name: gen-component
description: Generate React/Next.js frontend components from Stitch design screens. References the FRONTEND_DESIGN.md design tokens, color palette, typography, and component patterns to produce pixel-accurate Tailwind CSS components.
argument-hint: "[component-name] [screen: topology|selfhealing|ash|diagnosis]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate Frontend Component

You are generating a React component for the **NeuralDB** monitoring dashboard.

## Arguments
- Component name: $0
- Reference screen: $1 (optional)

## Design Reference
1. Read `docs/FRONTEND_DESIGN.md` for design tokens and component specs
2. If a screen is specified, read the corresponding HTML:
   - topology → `docs/screen1_topology.html`
   - selfhealing → `docs/screen2_selfhealing.html`
   - ash → `docs/screen3_ash.html`
   - diagnosis → `docs/screen4_diagnosis.html`
3. View the screenshot for visual reference:
   - `docs/screenshots/screen1_topology.png`
   - `docs/screenshots/screen2_selfhealing.png`
   - `docs/screenshots/screen3_ash.png`
   - `docs/screenshots/screen4_diagnosis.png`

## Component Generation Rules

### File Structure
```
frontend/src/components/{category}/{ComponentName}/
├── {ComponentName}.tsx        # Main component
├── {ComponentName}.types.ts   # TypeScript types/interfaces
└── index.ts                   # Re-export
```

### Design System Compliance
- Use Tailwind CSS utility classes matching design tokens
- Font: `font-headline` (Space Grotesk) for headings, `font-body` (Inter) for data
- Colors: Use semantic token names (`bg-surface-container`, `text-primary`, etc.)
- No 1px solid borders for sectioning (use background color shifts)
- Use glassmorphism (`glass-panel` class) for floating elements
- Use `neural-glow` for ambient shadows
- All transitions: `ease-out`, no bouncy/elastic animations

### Component Patterns
- Status badges: Use the badge patterns from FRONTEND_DESIGN.md Section 5.3
- Cards: Match card styles from Section 5.2
- Buttons: Match button styles from Section 5.1
- Progress bars: Match patterns from Section 5.4

### Code Standards
- TypeScript strict mode
- React 18+ functional components with hooks
- Props interface defined in `.types.ts`
- Use `cn()` utility for conditional classnames (clsx + tailwind-merge)
- Responsive: mobile-first with md/lg breakpoints
- Accessibility: proper ARIA labels, keyboard navigation
- Material Symbols Outlined for icons
