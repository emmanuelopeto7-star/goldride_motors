/** The landing-cost chain, mirrored from the server for live preview.
 *
 *  This is a deliberate duplication of `SourcedUnit`'s properties in
 *  backend/imports/models.py, and the only reason it exists is that a sourcing
 *  screen which cannot show a total until you save is not a calculator. Two
 *  rules keep the duplication honest:
 *
 *  1. The rates are never written here. They come from
 *     GET /api/staff/import-rates/, so a rate change on the server takes
 *     effect immediately rather than waiting for a redeploy.
 *  2. What this returns is a preview. The moment a unit is saved, every figure
 *     on screen comes from the server's response instead.
 *
 *  Each charge compounds on the last - excise sits on customs value plus duty,
 *  VAT on all three - so they cannot be collapsed into one summed rate.
 */

function num(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function landedCost(values, rates) {
  if (!rates) return null

  const unitPrice = num(values.unit_price_usd)
  const freight = num(values.freight_usd)
  const insurance = num(values.insurance_usd)
  const rate = num(values.dollar_rate)

  const cnfUsd = unitPrice + freight
  const cifUsd = cnfUsd + insurance
  const cnfKes = cnfUsd * rate
  const cifKes = cifUsd * rate

  // Blank means KRA has not valued it yet, and CIF is the right estimate
  // until an entry is lodged.
  const customsValue = values.customs_value_kes
    ? num(values.customs_value_kes)
    : cifKes

  const duty = (customsValue * num(rates.duty)) / 100
  const excise =
    ((customsValue + duty) * num(values.excise_rate ?? rates.excise_default)) / 100
  const vat = ((customsValue + duty + excise) * num(rates.vat)) / 100
  const idf = (customsValue * num(rates.idf)) / 100
  const rdl = (customsValue * num(rates.rdl)) / 100

  const taxes = duty + excise + vat + idf + rdl
  const clearing = num(values.clearing_kes)
  const fee = num(values.service_fee_kes)

  const landed = cifKes + taxes + clearing

  return {
    cnfUsd,
    cifUsd,
    cnfKes,
    cifKes,
    customsValue,
    duty,
    excise,
    vat,
    idf,
    rdl,
    taxes,
    clearing,
    fee,
    landed,
    total: landed + fee,
  }
}

/** What a unit would list at if pushed to stock. Landed cost plus margin,
 *  rounded up to the nearest thousand - never off the quoted total, which
 *  already carries a commission for the customer who walked away. */
export function stockPrice(landed, markupPercent) {
  const raw = landed * (1 + num(markupPercent) / 100)
  return Math.ceil(raw / 1000) * 1000
}
