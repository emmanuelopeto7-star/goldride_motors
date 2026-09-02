import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ColumnChart from '../../components/ColumnChart'
import ErrorState from '../../components/ErrorState'
import MethodShare from '../../components/MethodShare'
import Section from '../../components/Section'
import StatTile from '../../components/StatTile'
import { compactPrice, counted, formatPrice } from '../../lib/format'
import { WINDOWS, useStaffOverview } from '../../hooks/useStaffOverview'
import Button from '../../components/Button'

/** The owner's screen: how the business is doing, and what is stuck.
 *
 *  Every other tab answers "what do I do next". This one is the only place
 *  that reads across the tables - stock against cash against the queue - and
 *  it deliberately owns none of the work. Every count here is a link into the
 *  screen that can act on it; nothing on this page changes anything.
 *
 *  Manager and owner only, matching the endpoint. Sales works the queue.
 */

const SERIES = [
  { key: 'card', label: 'Card', shade: 'ink' },
  { key: 'mpesa', label: 'M-PESA', shade: 'soft' },
  { key: 'manual', label: 'Bank transfer', shade: 'mute' },
]

function StaffOverview() {
  const [searchParams, setSearchParams] = useSearchParams()
  const months = Number(searchParams.get('months') ?? 12)
  const [showTable, setShowTable] = useState(false)

  const { data, isLoading, isError, error, refetch } = useStaffOverview({ months })

  const setWindow = (value) => {
    const next = new URLSearchParams(searchParams)
    if (value === 12) next.delete('months')
    else next.set('months', String(value))
    setSearchParams(next)
  }

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((slot) => (
            <div key={slot} className="h-44 animate-pulse bg-line" />
          ))}
        </div>
        <div className="h-80 animate-pulse bg-line" />
      </div>
    )
  }

  if (isError) {
    return (
      <ErrorState
        title="The overview could not be loaded"
        message={error?.response?.data?.detail ?? 'Try again in a moment.'}
        onRetry={refetch}
      />
    )
  }

  const { stock, sourcing, collections, receivables, work, team } = data
  const trend = collections.months.map((month) => Number(month.total))

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <h2 className="font-serif text-h1">Overview</h2>
          <p className="mt-2 text-meta text-ink-soft">
            Every figure here is read-only. The counts link to the screen that
            can act on them.
          </p>
        </div>

        <nav className="flex flex-wrap gap-6" aria-label="Reporting window">
          {WINDOWS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setWindow(value)}
              className={`text-meta transition-colors ${
                months === value
                  ? 'text-ink underline underline-offset-4'
                  : 'text-ink-soft hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      <div className="mt-10 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Collected this month"
          value={formatPrice(collections.this_month)}
          delta={collections.delta_percent}
          deltaFrom={formatPrice(collections.last_month)}
          trend={trend}
        />
        <StatTile
          label="Retail value of live stock"
          value={formatPrice(stock.available_value)}
          note={`${counted(stock.available_count, 'car')} available · ${formatPrice(
            stock.reserved_value,
          )} reserved`}
        />
        <StatTile
          label="Outstanding"
          value={formatPrice(receivables.outstanding)}
          note={`${formatPrice(receivables.billed)} billed across ${counted(
            receivables.open_orders,
            'open order',
          )}`}
        />
        <StatTile
          label="Waiting in the queue"
          value={String(work.open)}
          note={
            work.oldest_open_days === null
              ? 'Nothing open'
              : `Oldest has waited ${counted(work.oldest_open_days, 'day')}`
          }
        />
      </div>

      <Section
        as="h3"
        title="Collected, month by month"
        note="Cash that arrived, dated by when it cleared - not sales booked. Deposits and instalments both count."
        action={
          <Button
            variant="quiet"
            onClick={() => setShowTable((open) => !open)}
          >
            {showTable ? 'Hide the figures' : 'Show the figures'}
          </Button>
        }
      >
        <ColumnChart
          data={collections.months}
          series={SERIES}
          caption={`Money collected over the last ${counted(
            collections.months.length,
            'month',
          )}, split by how it was paid.`}
        />

        {/* Obligatory rather than optional: the lightest step in the ink ramp
            sits under the contrast floor, so the numbers must be readable
            somewhere that is not the chart. */}
        {showTable && (
          <div className="mt-8 overflow-x-auto">
            <table className="w-full min-w-[640px] text-meta">
              <thead>
                <tr className="border-b border-line text-left text-badge uppercase text-ink-soft">
                  <th scope="col" className="py-3 pr-6 font-normal">Month</th>
                  <th scope="col" className="py-3 pr-6 font-normal">Card</th>
                  <th scope="col" className="py-3 pr-6 font-normal">M-PESA</th>
                  <th scope="col" className="py-3 pr-6 font-normal">Bank</th>
                  <th scope="col" className="py-3 pr-6 font-normal">Refunded</th>
                  <th scope="col" className="py-3 font-normal">Total</th>
                </tr>
              </thead>
              <tbody>
                {collections.months.map((month) => (
                  <tr key={month.month} className="border-b border-line">
                    <th scope="row" className="py-3 pr-6 text-left font-normal">
                      {month.label} {month.year}
                    </th>
                    <td className="py-3 pr-6 text-ink-soft">{compactPrice(month.card)}</td>
                    <td className="py-3 pr-6 text-ink-soft">{compactPrice(month.mpesa)}</td>
                    <td className="py-3 pr-6 text-ink-soft">{compactPrice(month.manual)}</td>
                    <td className="py-3 pr-6 text-ink-soft">{compactPrice(month.refunded)}</td>
                    <td className="py-3">{formatPrice(month.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <div className="grid gap-x-16 gap-y-0 lg:grid-cols-2">
        <Section
          as="h3"
          title="How the money arrives"
          note="Paystack refuses large amounts and M-PESA stops at 250,000, so the bank share is the trade the automated rails cannot carry."
        >
          <MethodShare months={collections.months} />
        </Section>

        <Section as="h3" title="What is stuck">
          <dl className="space-y-4">
            <Row
              label="Unclaimed"
              value={work.unclaimed}
              to="/staff/tickets"
              note="Nobody has picked these up."
            />
            <Row
              label="Claimed but untouched for two days"
              value={work.stale_claims}
              to="/staff/tickets"
              note="Owned by somebody who has stopped working them."
            />
            <Row
              label="Payments raised but never sent"
              value={receivables.awaiting_dispatch}
              to="/staff/payments?status=pending"
              note="The customer has not been told how to pay."
            />
            <Row
              label="Listings with no photograph"
              value={stock.without_photo}
              to="/staff/inventory"
              note="They are live on the site as they are."
            />
            <Row
              label="Listings lapsing this week"
              value={stock.expiring_soon}
              to="/staff/inventory"
            />
          </dl>
        </Section>
      </div>

      <Section
        as="h3"
        title="Capital in sourcing"
        note="Units chosen by a customer and paid for abroad, but not yet stock. Landed cost, which is what they cost us - not what they will be listed at."
      >
        <p className="font-serif text-section">{formatPrice(sourcing.capital)}</p>
        <p className="mt-2 text-meta text-ink-soft">
          Across {counted(sourcing.unit_count, 'unit')} not yet pushed to stock.
        </p>
      </Section>

      <Section
        as="h3"
        title="The team"
        note="Who can sign in, and what they have handled. A deactivated account stays listed - their name is on decisions."
        action={
          <Link
            to="/staff/settings"
            className="text-meta text-ink underline underline-offset-4"
          >
            Manage the team
          </Link>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-meta">
            <thead>
              <tr className="border-b border-line text-left text-badge uppercase text-ink-soft">
                <th scope="col" className="py-3 pr-6 font-normal">Name</th>
                <th scope="col" className="py-3 pr-6 font-normal">Role</th>
                <th scope="col" className="py-3 pr-6 font-normal">Claimed now</th>
                <th scope="col" className="py-3 pr-6 font-normal">Closed</th>
                <th scope="col" className="py-3 font-normal">Payments recorded</th>
              </tr>
            </thead>
            <tbody>
              {team.map((person) => (
                <tr key={person.id} className="border-b border-line">
                  <th scope="row" className="py-4 pr-6 text-left font-normal">
                    <span className={person.is_active ? '' : 'text-ink-mute'}>
                      {person.name}
                    </span>
                    {!person.is_active && (
                      <span className="ml-3 rounded-full border border-line px-3 py-1 text-badge uppercase text-ink-mute">
                        Deactivated
                      </span>
                    )}
                  </th>
                  <td className="py-4 pr-6 text-ink-soft">{person.role}</td>
                  <td className="py-4 pr-6">{person.tickets_claimed}</td>
                  <td className="py-4 pr-6 text-ink-soft">{person.tickets_closed}</td>
                  <td className="py-4">{person.payments_recorded}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

/** A count that is also a way in. Nothing on this screen acts; it points. */
function Row({ label, value, note, to }) {
  return (
    <div className="flex items-baseline gap-4 border-b border-line pb-4">
      <dt className="flex-1">
        <Link to={to} className="text-meta text-ink underline underline-offset-4">
          {label}
        </Link>
        {note && <p className="mt-1 text-meta text-ink-mute">{note}</p>}
      </dt>
      <dd
        className={`font-serif text-price ${
          value > 0 ? 'text-ink' : 'text-ink-mute'
        }`}
      >
        {value}
      </dd>
    </div>
  )
}

export default StaffOverview
