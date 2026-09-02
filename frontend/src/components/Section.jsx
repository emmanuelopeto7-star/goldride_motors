/** A titled block of a page, with the §3.5 rhythm.
 *
 *  Written down as a component because it had already drifted: the overview
 *  screen separated sections with 64px above a rule and 48 below, the dealer
 *  application form with 32 and 32, and a ticket panel with 32 and 24. All
 *  three are the same idea, and three spacings for one idea is how a site
 *  starts looking assembled rather than designed.
 *
 *  Page level only. A block nested inside a card wants a tighter rule - see
 *  §3.5 - because page rhythm inside a 24px card reads as a gap, not a break.
 */
function Section({
  title,
  note,
  action,
  children,
  first = false,
  // The heading level, not the size. A section inside a screen that already
  // has its own title is a level below it - the size stays `text-section`
  // either way, because the visual hierarchy and the document outline are
  // different questions.
  as: Heading = 'h2',
}) {
  return (
    <section className={first ? '' : 'mt-16 border-t border-line pt-12'}>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div>
          <Heading className="font-serif text-section">{title}</Heading>
          {note && (
            <p className="mt-2 max-w-[560px] text-meta text-ink-soft">{note}</p>
          )}
        </div>
        {action}
      </div>

      <div className="mt-8">{children}</div>
    </section>
  )
}

export default Section
