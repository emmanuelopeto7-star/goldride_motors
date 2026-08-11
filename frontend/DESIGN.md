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
5. Section rhythm: 64–96px · grid gutter 24px.

## 4. Header

1. 72px tall, sticky, white, 1px bottom border.
2. **Row 1:** hamburger 24px · serif wordmark 22px letterspaced · search pill
   (620px max, 44px tall, `#F4F2EE`) · "Sell With Us" link · auth pill (40px, bordered).
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
