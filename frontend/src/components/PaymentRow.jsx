import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import api from '../api/client'
import { formatPrice } from '../lib/format'
import { errorMessages } from '../lib/errors'
import Button from './Button'

const STATUS_LABEL = {
  pending: 'Awaiting payment',
  paid: 'Paid',
  failed: 'Failed',
  refunded: 'Refunded',
}

function PaymentRow({ payment, onPushSent }) {
  const [phone, setPhone] = useState('')
  const [sent, setSent] = useState(false)

  const dispatch = useMutation({
    mutationFn: async () => {
      const body = payment.method === 'mpesa' && phone ? { phone } : {}
      const res = await api.post(`/api/payments/mine/${payment.reference}/pay/`, body)
      return res.data
    },
    onSuccess: (data) => {
      if (data.checkout_url) {
        // Leaving the site is the point: the browser never decides the outcome.
        window.location.href = data.checkout_url
        return
      }
      setSent(true)
      onPushSent?.()
    },
  })

  const pending = payment.status === 'pending'
  const manual = payment.method === 'manual'

  return (
    <div className="border-t border-line py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-price font-semibold">{formatPrice(payment.amount)}</p>
        <p className="text-badge uppercase text-ink-soft">
          {STATUS_LABEL[payment.status] ?? payment.status} · {payment.method}
        </p>
      </div>

      {payment.note && (
        <p className="mt-2 text-meta text-ink-soft">{payment.note}</p>
      )}

      {manual && pending && (
        <p className="mt-3 text-meta text-ink-soft">
          This amount is settled by bank transfer — our team will send account
          details and confirm once it clears.
        </p>
      )}

      {pending && !manual && (
        <div className="mt-3 space-y-3">
          {payment.method === 'mpesa' && (
            <input
              type="tel"
              aria-label="M-PESA number"
              placeholder="M-PESA number, e.g. 2547XXXXXXXX"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className="h-11 w-full max-w-[320px] border border-line bg-surface px-4 text-meta outline-none focus:border-ink"
            />
          )}

          <div className="flex flex-wrap items-center gap-4">
            <Button
              variant="secondary"
              onClick={() => dispatch.mutate()}
              disabled={dispatch.isPending}
            >
              {dispatch.isPending
                ? 'Sending…'
                : payment.method === 'card'
                  ? 'Pay by card'
                  : 'Send M-PESA prompt'}
            </Button>

            {sent && (
              <p className="text-meta text-ink-soft">
                Check your phone and enter your PIN. This page updates itself.
              </p>
            )}
          </div>

          {dispatch.isError && (
            <p className="text-meta">{errorMessages(dispatch.error)[0]}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default PaymentRow
