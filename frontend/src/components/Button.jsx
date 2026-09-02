import { Link } from 'react-router-dom'

/** The one button.
 *
 *  Written down because the classes had already drifted: `h-11 px-6`,
 *  `h-12 px-8` and `h-12 px-10` were all in use for the same weight of
 *  action, and a `<Link>` dressed as a button carried `pt-3.5` to fake the
 *  vertical centring a flex box gives for free - which breaks the moment the
 *  label wraps.
 *
 *  Three weights, and the distinction is what the action costs rather than how
 *  important it looks:
 *
 *    primary    filled ink. The thing this screen exists to do.
 *    secondary  outlined. A real action, but not the one being encouraged.
 *    quiet      an underlined link. Reversible, or a way out.
 *    pill       the 40px rounded control in a header row (§4.2). Sentence
 *               case, because it sits beside sentence-case nav links rather
 *               than among uppercase page actions.
 *
 *  §4.7's focus ring is here rather than on each call site, which is why it
 *  had reached the header and nowhere else. `outline-current` follows the text
 *  colour so it inverts on a filled button without a second rule - except on
 *  primary, where the ring sits outside the fill on the page behind it and
 *  would be white on white.
 */

const FOCUS =
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2'

const VARIANTS = {
  primary: `bg-ink text-surface ${FOCUS} focus-visible:outline-ink`,
  secondary: `border border-ink ${FOCUS} focus-visible:outline-current`,
  quiet: `text-ink underline underline-offset-4 ${FOCUS} focus-visible:outline-current`,
}

// Its own base: sentence case at 13px, not the uppercase 11px a page action
// wears. The border colour is left to the caller, because the header inverts
// it over the hero.
const PILL = `inline-flex h-10 shrink-0 items-center rounded-full border px-5 text-meta transition-colors duration-200 ${FOCUS} focus-visible:outline-current`

const SIZES = {
  // 44px. The row-level size, where several sit together.
  default: 'h-11 px-6',
  // 48px. A page's own action, standing alone.
  large: 'h-12 px-8',
}

function classesFor({ variant, size, className }) {
  if (variant === 'quiet') {
    return `text-meta ${VARIANTS.quiet} ${className}`.trim()
  }

  if (variant === 'pill') {
    return `${PILL} ${className}`.trim()
  }

  return [
    // inline-flex, not a line-height guess: the label is centred whether it
    // wraps or not, and a Link gets the same treatment as a button.
    'inline-flex shrink-0 items-center justify-center text-badge uppercase',
    'transition-colors disabled:opacity-50',
    SIZES[size] ?? SIZES.default,
    VARIANTS[variant] ?? VARIANTS.primary,
    className,
  ]
    .filter(Boolean)
    .join(' ')
}

function Button({
  variant = 'primary',
  size = 'default',
  to,
  href,
  className = '',
  children,
  ...rest
}) {
  const classes = classesFor({ variant, size, className })

  if (to) {
    return (
      <Link to={to} className={classes} {...rest}>
        {children}
      </Link>
    )
  }

  if (href) {
    return (
      <a href={href} className={classes} {...rest}>
        {children}
      </a>
    )
  }

  // type defaults to "submit" inside a form, which has surprised somebody on
  // every project that did not set it.
  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  )
}

export default Button
