# Sachin's Work of Today

Date: 2026-04-04
Project: NagarDrishti
Prepared for: Sachin

## Overview

Today’s work focused on stabilizing the NagarDrishti frontend, wiring stitched HTML pages together properly, connecting the main UI to Flask routes, reducing broken or fake/demo behavior, and improving the user-facing experience across AI Detection, Manual Report, History, and Live View screens.

The major goal was to make the stitched frontend behave like one connected application instead of separate static mockup pages.

## Main Areas Completed

1. Frontend page wiring and route integration
2. Upload UI fixes
3. Notification UI improvements
4. Send-mail and department navigation flow
5. Real database-backed homepage stats
6. History page filtering fix for real DB statuses
7. Cleanup of dead links and disconnected pages

## Detailed Work Done

### 1. Connected stitched frontend pages with Flask

Work was done to make the pages inside `frontend/stitch_pages` behave as part of the Flask app instead of isolated HTML screens.

Changes included:

- Updated `frontend/app.py` to serve the stitched pages as Flask templates.
- Added and organized routes for the main application screens:
  - `/`
  - `/ai-detection`
  - `/ai-detection/verified`
  - `/ai-detection/rejected`
  - `/manual-report`
  - `/manual-report/submitted`
  - `/complaint-map`
  - `/history`
  - `/history/<complaint_id>`
- Added supporting API routes already used by the UI:
  - `/api/complaints`
  - `/api/complaints/geo`
  - `/api/analyze`
  - `/api/resend-email/<complaint_id>`
  - `/api/manual-report`

Impact:

- Main user navigation now goes through Flask routing.
- Core screens are reachable through actual app URLs.
- Complaint history and complaint detail pages can work with real complaint records.

### 2. Fixed broken navigation and disconnected frontend screens

Several HTML pages existed as stitched mockups but were not properly linked to one another or to the main landing page.

Work completed:

- Checked the frontend screens one by one.
- Removed dead placeholder navigation behavior such as non-working links and disconnected button flows.
- Wired main navigation between:
  - Home
  - AI Detection
  - Manual Report
  - Complaint Map / Live View
  - History
- Made the homepage feature cards clickable and routed them into real application pages.
- Added a proper destination for the “Municipal Depts Connected” area.

Impact:

- The application now feels connected instead of mock-based.
- The main landing page routes users into working screens.

### 3. Upload section UI fixes

There were visible UI issues in the upload sections, especially where stitched HTML had collapsed or broken upload boxes.

Fixes completed:

- Repaired the upload UI in AI Detection.
- Repaired the upload UI in Manual Report.
- Fixed the alignment and width behavior of upload containers.
- Ensured selected file information appears after file selection.
- Added visible file selection indicators such as filename and file size.
- Kept all changes minimal and preserved the existing layout and visual pattern.

Impact:

- Upload areas no longer appear broken or collapsed.
- Users now get immediate visual confirmation when a file is chosen.

### 4. Added notification box behavior

The previous notification behavior was either missing, weak, or not presented in a clear UI panel.

Changes completed:

- Added notification interactions in frontend pages where needed.
- Changed notifications from plain/toast-like loose behavior into small box/panel style interactions.
- Applied notification behavior to the main relevant pages, including AI Detection and Manual Report flows.

Impact:

- Notification icons now feel interactive.
- Alerts are shown in a more visible and structured UI format.

### 5. Added send-mail flow and department selection UI

The app previously lacked a clear and visible flow for department-based routing and sending mail across the main pages.

Work completed:

- Added the send-mail selection UI to `frontend/stitch_pages/tab1_verified.html`.
- Included:
  - Auto Select Department option
  - Manual Selection option
  - Department dropdown for manual choice
  - Dynamic display for selected department and email
- Confirmed the verified result screen acts as the existing mail-capable screen.

Impact:

- Users now have a visible send-mail control flow on the verified result screen.
- The UI better matches the intended complaint escalation process.

### 6. Created a connected departments page

There was no real page behind the “Municipal Depts Connected” idea. That gap was fixed.

Work completed:

- Added a new Flask route in `frontend/app.py`:
  - `/departments`
- Added a new frontend file:
  - `frontend/stitch_pages/departments.html`
- Built department context in Flask using complaint records.
- Rendered connected departments on a dedicated page.
- Added links from major pages to the departments page.

Impact:

- The “department connected” concept now has an actual destination page.
- The page acts as a directory and entry point for connected complaint-routing departments.

### 7. Added visible Departments and Send Mail entry points on core pages

The user specifically reported that the following pages did not provide access to department and send-mail behavior:

- History
- AI Detection
- Manual Report
- Live View / Complaint Map

That was fixed by adding visible actions to those screens.

Updated pages:

- `frontend/stitch_pages/tab1_initial.html`
- `frontend/stitch_pages/tab2_form.html`
- `frontend/stitch_pages/tab3_map.html`
- `frontend/stitch_pages/tab4_history.html`

What was added:

- A `Departments` button linking to `/departments`
- A `Send Mail` button linking to `/ai-detection/verified`

Impact:

- The send-mail and department flow is now reachable from the major core pages.
- The user no longer has to guess where those features exist.

### 8. Replaced fake homepage numbers with real DB-backed values

The main UI page had demo numbers such as complaint counts and department counts that were not based on the database.

Work completed:

- Added `build_home_stats()` in `frontend/app.py`.
- Pulled complaint data from the database through the existing safe complaint fetcher.
- Computed:
  - total complaints
  - verified complaint percentage
  - number of connected departments
- Passed the computed values into `frontend/stitch_pages/home.html`.
- Replaced fake values with Jinja-rendered values from real DB-backed complaint data.

Impact:

- Homepage statistics are no longer fake.
- The landing page now reflects actual stored complaint data.

### 9. Fixed complaint history filtering for real database statuses

The history page had a bug where changing the status filter did not correctly reflect real database values.

Problem:

- The status filter relied on exact string matching.
- Real DB values can vary in casing or formatting.
- That caused filters such as `Pending`, `In Progress`, `Resolved`, and `Rejected` to fail or behave inconsistently.

Fix completed:

- Added `normalizeHistoryStatus()` in `frontend/stitch_pages/tab4_history.html`.
- Normalized both:
  - dropdown-selected status
  - row status from the database
- Handled values such as:
  - `resolved`
  - `Rejected`
  - `in progress`
  - `in_progress`
  - `progress`
  - blank or fallback statuses
- Ensured `All Statuses` still shows everything.
- Triggered filter initialization on page load.

Impact:

- The status filter now works correctly with realistic DB values.
- History filtering is more robust against inconsistent status formatting.

### 10. Strengthened history and detail flow

The complaint history and complaint detail area was made more useful and connected.

Work completed:

- History page uses complaint data from Supabase through Flask.
- Complaint detail page can load from complaint public ID.
- Added fallback logic so the detail page can still render if full DB data is unavailable.
- History table rows route users into the complaint detail view.

Impact:

- Complaint tracking flow is more practical and user-friendly.
- Users can move from list view to detail view with real complaint context.

### 11. Cleaned older/demo page behavior

Older stitched/demo pages contained fake content, dead CTAs, broken placeholder links, and disconnected behavior.

Cleanup work included:

- Checking the `frontend` folder and `frontend/stitch_pages` structure for disconnected screens.
- Reducing dead links such as empty `href="#"` placeholders.
- Rewiring old demo/dashboard-style pages into the real Flask flow where possible.
- Removing dependency on machine-specific absolute paths in helper scripts used around stitched pages.

Impact:

- The frontend is now much cleaner and closer to a real application flow.
- Older screens are less misleading and less likely to trap the user in dead-end navigation.

## Key Files Worked On

### Backend / Flask integration

- `frontend/app.py`

Main backend-facing frontend work done here:

- Flask template routing
- homepage DB stats
- departments page route
- history and detail routing
- JSON APIs used by frontend screens

### Frontend templates

- `frontend/stitch_pages/home.html`
- `frontend/stitch_pages/tab1_initial.html`
- `frontend/stitch_pages/tab1_verified.html`
- `frontend/stitch_pages/tab2_form.html`
- `frontend/stitch_pages/tab3_map.html`
- `frontend/stitch_pages/tab4_history.html`
- `frontend/stitch_pages/complaint_detail.html`
- `frontend/stitch_pages/departments.html`
- `frontend/stitch_pages/ai_detection.html`
- `frontend/stitch_pages/manual_report.html`

### Supporting data access

- `database/supabase_client.py`

Used for complaint retrieval and DB-backed frontend display behavior.

## Summary of User-Facing Improvements

By the end of today’s work:

- The frontend is better connected page to page.
- Main navigation works more like a real app.
- Upload sections are more stable and usable.
- File selection feedback is visible.
- Notification panels are clearer.
- Department and send-mail access is visible from major screens.
- The homepage shows real DB-backed stats instead of placeholder numbers.
- The history status filter works with real DB data.

## Notes

- The overall layout and stitched design pattern were preserved wherever the request asked for minimal changes.
- Most UI changes were intentionally small and targeted rather than redesigning screens.
- The focus remained on functional repair, wiring, realistic data usage, and improving user flow.

## Final Outcome

Today’s work significantly improved the NagarDrishti frontend from a partially stitched prototype into a more connected and working application interface, especially around:

- routing
- upload flow
- data realism
- department escalation visibility
- history usability
- send-mail discoverability

This work lays a much stronger foundation for final frontend polish and full end-to-end testing.
