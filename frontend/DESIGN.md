# Goldride Design Rules

The single source of truth for the frontend's look. Cite rules by section + number
in review ("breaks §3.2 — cards must have radius 0").

## 1. Type

| Rule           | Value                                                                     |
| -------------- | ------------------------------------------------------------------------- |
| Display serif  | Playfair Display / Cormorant / Libre Baskerville — wordmark, H1, section titles only |
| UI sans        | Inter / system stack — everything else                                    |
| H1             | 44px / 1.1                                                                |
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
5. Section rhythm: 64–96px · grid gutter 24px.

## 4. Header

1. 72px tall, sticky, white, 1px bottom border.
2. **Row 1:** hamburger 24px · serif wordmark 22px letterspaced · search pill
   (620px max, 44px tall, `#F4F2EE`) · "Sell With Us" link · auth pill (40px, bordered).
3. **Row 2:** brand strip 48px, sans 14px, 24px gaps, horizontal scroll with fading
   edges, active item underlined.

## 5. Hero

1. Full-bleed · 420px desktop, 280px mobile.
2. Left-to-right dark scrim, `0.45 → 0`.
3. Serif H1, white, bottom-left, 48px inset.
4. Subline 11px uppercase, white 80%, 480px max-width, carries the live inventory count.

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

1. Make tile: 1:1, bordered, logo at 60% width, greyscale → colour on hover; 8 / 4 / 3 across.
2. Model card: 88px square thumb left, name 15px + "N LISTINGS" 11px uppercase, chevron right.
3. Carousel arrows: 40px bordered circles, top-right of section.

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
