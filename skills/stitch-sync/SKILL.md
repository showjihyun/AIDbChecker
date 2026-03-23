---
name: stitch-sync
description: Sync UI designs from Google Stitch MCP. Fetches the latest screens, screenshots, and design system updates from the Stitch project and updates local design documentation and HTML references.
disable-model-invocation: true
argument-hint: "[screen-id|all]"
allowed-tools: Read, Write, Glob, Edit, Bash, mcp__stitch__get_project, mcp__stitch__list_screens, mcp__stitch__get_screen
---

# Stitch Design Sync

Sync the latest designs from Google Stitch into the local project.

## Arguments
- Screen ID or "all": $ARGUMENTS (default: all)

## Stitch Project
- **Project ID**: `11640044698331273458`
- **Project Name**: "AI Diagnosis & RCA Panel"

## Sync Steps

### Step 1: Fetch Project Info
Use `mcp__stitch__get_project` with name `projects/11640044698331273458` to get:
- Updated design theme (colors, fonts, spacing)
- Screen list with current versions

### Step 2: Fetch Screens
Use `mcp__stitch__list_screens` with projectId `11640044698331273458`.
For each design screen (type: DESKTOP with screenshots), use `mcp__stitch__get_screen`.

### Step 3: Download Assets
For each screen with HTML code:
- Download HTML to `docs/screen{N}_{name}.html`
- Download screenshot to `docs/screenshots/screen{N}_{name}.png`

### Step 4: Update Design Document
Compare fetched design theme with current `docs/FRONTEND_DESIGN.md`:
- Update color tokens if changed
- Update typography if changed
- Update component patterns if new screens added
- Add changelog entry at bottom of document

## Screen Mapping
| Screen | File | Title |
|--------|------|-------|
| 1 | screen1_topology | Full-Stack Topology Dashboard |
| 2 | screen2_selfhealing | Self-Healing & Playbook Management |
| 3 | screen3_ash | 1s ASH & Wait Event Explorer |
| 4 | screen4_diagnosis | AI Diagnosis & RCA Panel |

## Output
- Updated HTML files in `docs/`
- Updated screenshots in `docs/screenshots/`
- Updated `docs/FRONTEND_DESIGN.md` if design tokens changed
- Summary of changes printed to console
