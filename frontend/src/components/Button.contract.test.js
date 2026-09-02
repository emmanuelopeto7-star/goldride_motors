import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { cwd } from 'node:process'
import { describe, expect, it } from 'vitest'

/** The migration, kept.
 *
 *  Button sat unused for a while after it was written: `h-11 px-6 …` had been
 *  copied into 35 other files, one of them written *after* the component. A
 *  component nobody reaches for is not a system, so this is the part that
 *  notices - and it reads the source, because the drift is invisible to a
 *  rendering test that only ever mounts the file it is about.
 *
 *  It looks at <button> openings rather than whole files on purpose. Ink on
 *  white is not the button's to own: a chat bubble, a badge and the footer are
 *  all `bg-ink text-surface` and none of them is a control.
 */

// jsdom gives import.meta.url an http: scheme, so the root comes from where
// vitest was started rather than from this file's own location.
const SRC = join(cwd(), 'src')

// The launcher is a 56px floating control carrying a count badge - one of a
// kind, and a third size invented for one button would be the drift, not the
// cure. Modal's close and the LinkedIn button fall out on their own: an icon
// and a provider's own chrome never claimed to be one of the three weights.
const ALLOWED = new Set(['components/ChatLauncher.jsx'])

function sources(dir = SRC, found = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) sources(path, found)
    else if (name.endsWith('.jsx') && !name.includes('.test.')) found.push(path)
  }
  return found
}

/** Every <button …> opening tag in the app, with the file it came from. */
function buttonTags() {
  const tags = []
  for (const path of sources()) {
    const name = relative(SRC, path).split(sep).join('/')
    if (ALLOWED.has(name)) continue
    const text = readFileSync(path, 'utf8')
    for (const match of text.matchAll(/<button\b[^>]*>/gs)) {
      tags.push({ name, tag: match[0] })
    }
  }
  return tags
}

describe('the button contract', () => {
  it('has no <button> dressed as one of the three weights by hand', () => {
    const dressed = buttonTags().filter(
      ({ tag }) =>
        /\bbg-ink\b[^"]*\btext-surface\b/.test(tag) ||
        /\bborder border-ink\b/.test(tag) ||
        /\bunderline underline-offset-4\b/.test(tag),
    )

    expect(dressed.map(({ name }) => name)).toEqual([])
  })

  it('leaves the two agreed heights the only ones, so nothing invents a third', () => {
    const sized = buttonTags().filter(
      ({ tag }) => /\bh-\d+\b/.test(tag) && /text-badge uppercase/.test(tag),
    )

    expect(sized.map(({ name, tag }) => `${name}: ${tag.match(/\bh-\d+\b/)[0]}`)).toEqual([])
  })
})
