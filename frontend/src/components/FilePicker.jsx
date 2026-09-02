import { counted } from '../lib/format'
import Button from './Button'

/** Choosing files before there is anything on the server to attach them to.
 *
 *  The dealer portal uploads a photograph the moment it is picked, because the
 *  car already exists. An application does not: nothing has been created yet,
 *  so the files are held in component state and travel with the submission.
 *  That means this has to show what is queued and let one be taken back out -
 *  a bare <input type="file"> shows a count and nothing else, and "3 files"
 *  is not enough to notice you attached the wrong one.
 *
 *  `labels` turns the list into labelled entries: paperwork needs to say which
 *  document each file is, photographs do not.
 */
function FilePicker({
  label,
  hint,
  accept,
  max,
  files,
  onChange,
  labels = null,
  noun = 'file',
  checklist = [],
}) {
  const atLimit = files.length >= max
  const attached = new Set(files.map((entry) => entry.kind))
  const labelFor = labels ? Object.fromEntries(labels) : {}

  function add(event) {
    const chosen = [...event.target.files]
    const room = max - files.length
    const entries = chosen
      .slice(0, room)
      .map((file) => (labels ? { file, kind: labels[0][0] } : file))

    onChange([...files, ...entries])
    // Cleared so the same file can be picked again after removing it -
    // otherwise onChange never fires a second time for that name.
    event.target.value = ''
  }

  function remove(index) {
    onChange(files.filter((_, position) => position !== index))
  }

  function relabel(index, kind) {
    onChange(
      files.map((entry, position) =>
        position === index ? { ...entry, kind } : entry,
      ),
    )
  }

  return (
    <div>
      <p className="text-badge uppercase text-ink-soft">{label}</p>
      {hint && <p className="mt-2 text-meta text-ink-mute">{hint}</p>}

      {/* Ticked as each one arrives. A list of seven documents with no
          indication of which are done is a list somebody gives up on. */}
      {checklist.length > 0 && (
        <ul className="mt-4 space-y-2">
          {checklist.map((kind) => {
            const done = attached.has(kind)
            return (
              <li key={kind} className="flex items-center gap-3 text-meta">
                <span
                  aria-hidden="true"
                  className={`flex h-4 w-4 shrink-0 items-center justify-center border text-[10px] ${
                    done
                      ? 'border-ink bg-ink text-surface'
                      : 'border-line text-transparent'
                  }`}
                >
                  ✓
                </span>
                <span className={done ? 'text-ink' : 'text-ink-soft'}>
                  {labelFor[kind] ?? kind}
                </span>
                <span className="sr-only">
                  {done ? 'attached' : 'still needed'}
                </span>
              </li>
            )
          })}
        </ul>
      )}

      {files.length > 0 && (
        <ul className="mt-6 space-y-3">
          {files.map((entry, index) => {
            const file = labels ? entry.file : entry
            return (
              <li
                key={`${file.name}-${index}`}
                className="flex flex-wrap items-center gap-4 border border-line p-3"
              >
                <span className="min-w-0 flex-1 truncate text-meta">
                  {file.name}
                </span>

                {labels && (
                  <select
                    value={entry.kind}
                    onChange={(event) => relabel(index, event.target.value)}
                    aria-label={`What ${file.name} is`}
                    className="h-10 border border-line bg-surface px-3 text-meta outline-none focus:border-ink"
                  >
                    {labels.map(([key, text]) => (
                      <option key={key} value={key}>
                        {text}
                      </option>
                    ))}
                  </select>
                )}

                <Button
                  variant="quiet"
                  onClick={() => remove(index)}
                >
                  Remove
                </Button>
              </li>
            )
          })}
        </ul>
      )}

      <label
        className={`mt-4 inline-block px-6 py-3 text-badge uppercase ${
          atLimit
            ? 'cursor-not-allowed border border-line text-ink-mute'
            : 'cursor-pointer border border-ink'
        }`}
      >
        {atLimit ? `That is ${counted(max, noun)}` : `Add ${noun}s`}
        <input
          type="file"
          multiple
          accept={accept}
          disabled={atLimit}
          onChange={add}
          className="hidden"
        />
      </label>
    </div>
  )
}

export default FilePicker
