# Product Spec: Mobile Responsiveness

DocFlow needs to be fully responsive, allowing users to view, upload, convert, and annotate documents directly from their mobile devices.

## User Experience (UX) Goals

1. **Seamless Layout on Small Screens**: The two-pane layout (`Control Panel` on the left, `Preview/Output` on the right) must adapt smoothly on screens smaller than 900px.
2. **Easy Navigation / Toggle Panels**: Users should be able to switch easily between the converter controls and the preview output area without zooming or horizontal scrolling.
3. **Optimized Dictionary and Annotations Popovers**:
   - The side-panel dictionary (`dict-panel`) should slide in as a full-screen drawer or drawer from the bottom/right.
   - Popovers (like annotations toolbar, stamp editing panel) must fit within mobile screen bounds.
4. **Touch-Friendly Controls**: Buttons and tools should have adequate tap targets (at least 44x44px where possible).

## Visual Layout Adaptations

### 1. Main Viewport & Shell
- Padding around `.shell` is reduced on mobile screens to maximize workspace area.
- Brand header scales down.

### 2. Workspace View Toggles
- Instead of showing both the Control Panel and the Preview side-by-side, we show them as single columns or tabbed panes.
- A floating toggle bar or segment button will allow the user to easily switch between:
  - **Configurações/Upload** (Painel de Controle)
  - **Visualização** (Preview do Documento)

### 3. Annotation and Stamp Tools
- The floating annotation toolbar and stamps should adapt so they do not overlap content awkwardly.
- Text selection and highlight controls should remain fully accessible via touch events.

## Validation / Success Criteria
- Zero horizontal scrolling on screens down to 320px width.
- Functional toggle menu or tabs to switch viewports.
- No panel overlaps or unreadable text columns.
