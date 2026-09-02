# Goldride Design Rules

The single source of truth for the frontend's look. Cite rules by section + number
in review ("breaks §3.2 — cards must have radius 0").

## 1. Type

| Rule           | Value                                                                     |
| -------------- | ------------------------------------------------------------------------- |
| Display serif  | Playfair Display / Cormorant / Libre Baskerville — wordmark, H1, section titles only |
| UI sans        | Inter / system stack — everything else                                    |
| H1             | 44px / 1.1                                                                |
| Hero headline  | 64px / 1.05 desktop, 36px mobile — §5 only                                 |
| Section title  | 32px / 1.2                                                                |
| Price          | 20px semibold                                                             |
| Model          | 15px                                                                      |
| Metadata       | 13px                                                                      |
| Badges         | 11px uppercase, 0.08em tracking                                           |

1. Serif is **never** below 24px.
2. Sans is **never** above 20px.

## 2. Colour

| Token          | Value     |
| -------------- | --------- |
| Page           | `#FAFAF8` |
| Surface        | `#FFFFFF` |
| Border         | `#E4E2DD` |
| Text primary   | `#1A1A1A` |
| Text secondary | `#6B6B6B` |
| Text muted     | `#9A9A9A` |

1. Links and active states: **black + underline**, never colour.
2. No gradients. No tinted backgrounds. The hero scrim (§5) is the one exception,
   and it is an overlay — not a background.

## 3. Geometry

1. Radius: `0` on cards and tiles · `999px` on pills · `50%` on icon buttons.
2. 1px `#E4E2DD` borders everywhere. Shadows **only** on open dropdowns.
3. Spacing scale: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96`.
4. Container: 1440px max · padding 48px desktop, 20px mobile.
5. Section rhythm: 64–96px · grid gutter 24px. **Use `components/Section.jsx`**
   rather than spacing a rule by hand — this had already drifted into three
   different rhythms for the same idea. A block *nested inside a card* is the
   exception and takes 24px above and below its rule: page rhythm inside a
   24px card reads as a gap rather than a break.

## 4. Header

1. 72px tall, sticky, white, 1px bottom border.
2. **Row 1:** hamburger 24px · serif wordmark 22px letterspaced · search pill
   (620px max, 44px tall, `#F4F2EE`) · text links · auth pill (40px, bordered).
   The links are `Staff` (sales only), `Import a car`, and the dealer route -
   **`List your cars` → `/list-with-us`** for everyone else, swapping to
   `Your cars` → `/dealer` once a dealer is signed in. This is the "Sell With
   Us" link this rule has always called for; it was built 2026-08-27, and
   named for what it does rather than for the transaction.
3. **Row 2:** brand strip 48px, sans 14px, 24px gaps, horizontal scroll with fading
   edges, active item underlined.
4. **Overlay mode.** On a page with a hero the header is transparent and sits *on*
   the image — no fill, no bottom border. Wordmark, brand strip, links and icons
   invert to white; the search pill becomes white at 15% with a white 25% border
   and white placeholder text.
5. Overlay ends on scroll. Once the page has moved more than 80px the header
   animates to its solid white state (rule 1) over 200ms and stays there.
6. Pages with no hero use the solid state from the first paint — there is no flash
   of transparent header.
7. **Underline in a nav means "you are here", not "this is a link."** §2.1
   gives underline to links *and* active states; used permanently on every nav
   item it says all of them are current, and leaves no mark for the one that
   is. So: `--color-ink-soft` at rest, `--color-ink` + underline on hover, and
   `--color-ink` + underline for the route you are on. Use `NavLink`, never a
   hand-rolled `isActive`.
   Over the hero the rest state stays **full white** and only the underline
   separates active from not — the footer may dim its links to 70% because it
   sits on a flat `#1A1A1A` whose contrast is a number you can check, but here
   the backdrop is whatever photograph was uploaded.
8. **Every header link carries a visible focus ring** (`focus-visible:outline`,
   2px, offset) and grows its hit target with `py-3 -my-3` — padding that
   enlarges the target without moving anything, because the row is centred in a
   fixed-height header. A 13px underlined link whose only focus state is the
   browser default is unusable by keyboard over a photographic hero. The same
   applies in the mobile menu, where rows are `py-3` rather than `py-2`, and
   to the staff tab bar, which was a 13px label with 12px under it and nothing
   above — a 34px target on a touchscreen.
   The ring is **`outline-current`**, never the browser default — that default
   is orange, and §2.2 has no colour in it. Following the text colour also
   makes the ring invert with the header in overlay mode for free. On an
   ink-filled button the ring sits outside the button on the page, so those
   set `outline-ink` explicitly; on the dark footer, `outline-white`.

## 5. Hero

1. Full-bleed, and it starts at the **top of the document**, behind the header —
   the header's 120px (72 + 48) overlays the image rather than sitting above it.
2. **Full viewport height** (`svh`, not `vh` — mobile browser chrome makes `vh`
   overshoot and crop the headline). The overlaid header eats the top 120px; the
   headline and subline sit against the bottom edge.
3. Left-to-right dark scrim, `0.45 → 0`. It has a second job in overlay mode:
   keeping the white wordmark and brand strip legible over the photograph.
4. Hero headline (§1) in the display serif, white, bottom-left, 48px inset
   desktop / 20px mobile.
5. Subline 11px uppercase, white 80%, **900px max-width**, wrapping to at most two
   lines, carrying the live inventory count.

### 5b. Hero video (optional)

1. A poster image is **always required**, video or not. It is the first paint, the
   mobile experience, and the fallback — never an afterthought.
2. `autoplay muted loop playsinline`. Autoplay without `muted` is blocked by every
   browser; without `playsinline` iOS takes over the screen.
3. Strip the audio track before upload rather than relying on `muted`.
4. Under 3MB, 6–10s, seamlessly looping, 1920×1080 is ample behind a scrim.
5. **Mobile shows the poster, not the video.** Below 768px the video never loads.
6. `prefers-reduced-motion: reduce` shows the poster. This is an accessibility
   setting people choose because motion makes them unwell, not a preference to
   second-guess.
7. Composition rules are unchanged: the left third stays calm for the whole loop,
   or the headline fights the footage every 8 seconds.

## 6. Listing card

1. 3-up desktop / 2-up tablet / 1-up mobile · image 4:3 cover.
2. Photo counter bottom-right — dark 70% pill, white 11px.
3. Favourite heart top-right — 32px white circle.
4. Status badge top-left — white pill, 11px uppercase.
5. Body padding 16px, in order: **price → year make model → location**.
6. Contact action right of the price row: envelope + label, 13px.
7. Dealer logo max 24px tall, bottom-right, greyscale until hover.
8. Hover: image scale `1.03` over 400ms, border → `#C9C6C0`.

## 7. Filter bar

1. Sticky below the header, 64px, white, bottom border.
2. Chips: 40px tall, 999px radius, 1px border, 16px padding, 12px gaps,
   14px label + 12px chevron.
3. Active chip: black fill, white label, count badge.
4. "Save search" separated to the right. Sort is a **text-button dropdown, not a chip**.

## 8. Make grid / model carousel

1. Make tile: 1:1, bordered, logo at 70% width in **full colour**, maker named
   beneath it, count below that; 8 / 4 / 3 across. Hover moves the border to
   `#1A1A1A` — the logo itself does not change.
   *Was greyscale-until-hover. Reversed 2026-08-19: manufacturer marks are the
   only colour on the page, and desaturating them made the grid read as
   disabled rather than restrained.*
2. The tile must stay square. The logo is a flex child that gives up height
   when a long name wraps — a fixed-height logo pushes the tile taller than it
   is wide and breaks the row.
3. Model card: 88px square thumb left, name 15px + "N LISTINGS" 11px uppercase, chevron right.
4. Carousel arrows: 40px bordered circles, top-right of section.

## 9. Modal

1. Scrim: ink at 50%, sitting above the sticky header.
2. Dialog: 440px max width, 1px `#E4E2DD` border, page surface, radius 0.
3. Padding 48px.
4. **No shadow** — the scrim does the separating, so §3.2 survives intact.
5. Title: display serif, 32px, centred.
6. Fields: 48px tall, 1px border, white fill, border goes to `#1A1A1A` on focus.
7. Primary action: 48px, black fill, white 11px uppercase label, full width.
8. Closes on Escape, on scrim click, and on the X. Body scroll locks while open,
   and unlocks on unmount.

### 9b. Image viewer

1. Full screen, edge to edge — a photograph is the content, not an illustration
   inside a card.
2. Surface is `#1A1A1A` at 95%, not white. Photographs need a neutral dark
   surround to be judged; this is the one place §2 gives way, and only because
   nothing here is chrome.
3. The image is **contained, never cropped**. Cropping is right for a card and
   wrong for a viewer.
4. Previous / next as 40px+ bordered circles at the vertical centre, white on
   the dark surface.
5. Arrow keys step through, Escape closes, and the position reads `3 / 12`.
6. Thumbnail strip along the bottom, 64px, current one outlined, the rest at
   50% opacity.

## 10. Footer

1. Surface `#1A1A1A`, text white — a deliberate exception to §2.2, because a long
   page needs a terminator and a white footer just trails off. Same class of
   exception as the hero scrim (§5.3) and the image viewer (§9b.2).
2. Four columns on desktop, two on tablet, stacked on mobile. 96px top margin,
   64–96px internal padding.
3. Column headings 11px uppercase at 50% white. Links 13px at 70%, going to
   100% on hover. No underlines here — the whole column is links, so underlining
   every one is noise rather than signal.
4. **Only links that resolve.** Browse and Makes are filter URLs, so they work.
   Nothing points at a page that does not exist yet.
5. Makes are pulled live from `/api/cars/makes/` with counts — the same query the
   filter bar uses, so it costs no extra request.
6. Bottom bar above a 15% white rule: copyright left, the good-faith notice right.
7. The dealer route (`/list-with-us`) appears here as a **bordered box**, not as
   one more link in the Contact column: a dealership reading the bottom of the
   page is on different business from everyone else reading an address. It is
   the second of two routes to that page — the header (§4.2) is the first.

## 11. Charts

Added with the staff Overview screen. Charts are the one place the rules of §2
cannot simply be applied - a palette with no hues has to carry quantity somehow -
so the exception is written down rather than left to whoever builds the next one.

1. **The ink ramp is the chart palette**: `#1A1A1A` -> `#6B6B6B` -> `#9A9A9A`,
   read as a **sequential** ramp (one hue, light to dark), never as a set of
   categorical colours. No hue is introduced for a chart. The three steps
   separate by DeltaE 15.8 at the closest adjacent pair, under both deutan and
   tritan simulation, against a target of 8 - so the steps are tellable apart.
2. **Identity never rests on the shade**, and a legend is always present for
   more than one series. `#9A9A9A` sits at **2.74:1** against
   the surface, under the 3:1 floor. Any chart with more than one series
   therefore ships direct labels *and* a table view of the same numbers. A
   single-series chart needs no key at all - the heading names it.
3. **The axis starts at zero** on anything with a bar in it, and is topped at a
   round number above the data, not at the data.
4. **Fills never touch**: 2px of surface between stacked segments and between
   neighbouring columns.
5. **The rounded end is 4px, on the data end only.** The baseline corner stays
   square - a bar rounded at the bottom floats off its own axis.
6. **Grid and axis are hairlines in `--color-line`**, never in ink. Axis figures
   are `--color-ink-mute` in a left gutter, clear of the first column.
7. **Values are printed selectively** - the latest point and the peak, never one
   on every column. Everything else is in the tooltip and the table.
7b. **A column chart of months carries four marks, not one.** A **trailing
   3-month average** in `--color-ink-soft` at 2px over the columns, because one
   large sale otherwise becomes the shape of the year; a **year divider** in
   `--color-line-hover` wherever the calendar year turns, because a 12-month
   window nearly always crosses one; a **dashed outline and a SO FAR label on
   the current month**, because it is a partial month standing against finished
   ones and unmarked it reads as a collapse - outlined to its own height, never
   to a projection; and a **crosshair** on the hovered band.
7c. **Columns rise from the baseline on first paint** (`.chart-rise`, 420ms),
   and not at all under `prefers-reduced-motion`.
8. **Text wears text tokens**, never the series colour. A swatch beside a label
   carries the identity; the label itself is ink.
9. **Every chart is hoverable**, and the hit target is the whole band rather
   than the mark - an empty month still has to answer when asked.
10. **No dual axes, ever.** Two measures on different scales are two charts.
11. Geometry lives in `lib/chartScale.js` and is unit-tested. Components draw;
    they do not calculate. Charts are hand-rolled SVG - a charting library
    arrives with rounded corners, tinted fills, shadows and a colour cycle, all
    of which contradict §2 and §3.

---

## 12. Buttons

Use `components/Button.jsx`. The classes had already drifted into `h-11 px-6`,
`h-12 px-8` and `h-12 px-10` for the same weight of action, and a `<Link>`
dressed as a button carried `pt-3.5` to fake vertical centring — which breaks
the moment a label wraps.

1. **Three weights**, chosen by what the action costs rather than by how
   important it looks:
   * `primary` — filled ink. The thing this screen exists to do.
   * `secondary` — outlined. A real action, but not the one being encouraged.
   * `quiet` — an underlined link. Reversible, or a way out.
2. **Two sizes and nothing between them**: `default` 44px for a row where
   several sit together, `large` 48px for a page's own action standing alone.
   The header's 40px rounded control is the `pill` variant — sentence case at
   13px, because it sits beside sentence-case nav links rather than among
   uppercase page actions. It had been defined once in the storefront header
   and hand-copied into the staff one, minus the transition and the ring.
3. **Labels are 11px uppercase**, letterspaced (`text-badge`), except `quiet`
   which is sentence case at 13px.
4. **The focus ring lives on the button**, not on the call site — §4.7 was
   written down and reached only the header precisely because it did not.
   `outline-current` follows the text colour and inverts for free; a filled
   button uses `outline-ink`, because its ring falls outside the fill onto the
   page, where `current` would be white on white.
5. `inline-flex` centring, never a padding guess, so a route and a button look
   identical and a wrapped label stays centred.
6. **A conditional weight is a prop, not a class string.** Where a button
   changes weight with state — approve vs reject, ask vs done — write
   `variant={approving ? 'primary' : 'secondary'}`. The template literal these
   replaced hid the button from every search for the classes.

### 12.1 What is deliberately not a Button

Three controls stay hand-written, because forcing them in would mean inventing
a size or a variant that exists for one call site:

* **`Modal`'s close** — a 32px round icon button carrying an `aria-label`, not
  a label in any of the three weights.
* **`SocialButtons`' LinkedIn button** — a provider's own chrome: its border,
  its mark, sentence case. Ours to place, not to restyle.
* **`ChatLauncher`** — a 56px floating control with a count badge, one of a
  kind.

`Button.contract.test.js` reads the source and fails on any *other* `<button>`
wearing one of the three weights or a height of its own. The component existed
for a while before anything used it — the classes had been copied into 35 more
files, one of them written after the component — so the rule needed something
that notices. A rendering test cannot: it only ever mounts the file it is about.

## 13. Two patterns the dealer work introduced

1. **Requirement checklist** (`FilePicker`, §the application form). A list of
   documents with a 16px box that fills with ink as each arrives. The state is
   also given as `sr-only` text — "attached" / "still needed" — because a tick
   is colour and shape only. The submit stays disabled while anything is
   outstanding, with the missing items named in text beneath it: a disabled
   button with no explanation is a dead end.
2. **Event timeline** (`PaymentHistory`). One `h-2 w-2` dot per event in
   `--color-line-hover`, filled `--color-ink` for anything a person did rather
   than a machine. Same dot as the order stage rail, so the two read as one
   idea. Each line is `from → to · source · who`, then the timestamp and the
   reason underneath in `--color-ink-mute`.

---

# Adding the hero image to the home page

**Sourcing**

1. One wide landscape shot of **your own inventory** — never a stock supercar that
   isn't on the lot.
2. 2880×1200 minimum, subject weighted **right** so the left third stays clear for
   the headline.

**Encoding**

3. AVIF with WebP fallback, three widths: **2880 / 1920 / 960**, quality ~70.
4. Under 250KB at the largest size.

**Backend**

5. Store as a `HeroBanner` model in Django — `image`, `headline`, `subline`, CTA link,
   `is_active` — so marketing swaps it without a deploy.
6. Expose it on the homepage endpoint.

**Markup**

7. `<picture>` with `srcset` + `sizes="100vw"`.
8. Add `<link rel="preload" as="image">` — the hero is the LCP element and must **not**
   be lazy-loaded. Everything below the fold is.
9. Mobile: swap to a **4:3 crop** via `<source media>` rather than letting the wide
   image squash. Headline inset drops to 20px.

**Layout & effects**

10. Reserve the space with a fixed aspect-ratio wrapper on a solid `#1A1A1A` background
    — zero layout shift while it loads.
11. Apply the scrim as a **CSS gradient overlay**, not baked into the file, so the same
    image survives a copy change.

---

## Not yet built

- `HeroBanner` model and homepage endpoint (§hero 5–6) do not exist in the backend.
  Build the hero against a static import first, swap to the endpoint later.
- Live inventory count (§5.4) can come from the `count` field of the paginated
  `/api/cars/` response in the meantime.
