# Tech Spec: Mobile Responsiveness

This document describes the technical implementation details to make DocFlow mobile responsive.

## Proposed Layout Changes

### 1. Viewport Meta Tag
Verify that `interface.html` has the standard viewport tag:
`<meta name="viewport" content="width=device-width, initial-scale=1.0">`

### 2. View Toggle Bar (CSS & JS)
On screens smaller than 900px, we will hide one of the main panels and show a tab navigation bar.
- Create a new header tab selector `#viewModeSelector` in `interface.html` containing two options:
  - **Upload/Ajustes** (shows `.control-panel`, hides `.output-wrapper`)
  - **Visualização** (shows `.output-wrapper`, hides `.control-panel`)
- Add corresponding CSS to hide the inactive panel and set `.workspace { grid-template-columns: 1fr; }` under `@media (max-width: 900px)`.

### 3. CSS Adjustments for Panels
- Reduce padding for `.shell` and headers.
- Make the main toolbar (`.annot-toolbar`) and popovers position relative to the screen or wrap appropriately so they do not clip outside viewport boundaries.
- Ensure the popover toast and modals have `max-width: 90vw` or use flex layouts.

### 4. Dictionary Drawer overlay
On screens under 768px, `.dict-panel` is already fixed. Let's make sure it transitions smoothly and doesn't conflict with main scrolling.

## Rollout & Risk Plan
- Risk: Hiding `.control-panel` might confuse users trying to edit settings while looking at the preview.
- Mitigation: Keep the toggle selector prominent at the top/bottom of the interface. When conversion succeeds, automatically switch view to the **Visualização** tab.
