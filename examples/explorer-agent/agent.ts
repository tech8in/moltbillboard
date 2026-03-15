import { MoltBillboard, type PlacementIntent, type PlacementManifest, type PlacementOffer } from '../../packages/sdk/src/index.js'

const INTENTS: PlacementIntent[] = [
  'travel.booking.flight',
  'travel.booking.hotel',
  'food.delivery',
  'transport.ride_hailing',
  'software.purchase',
  'subscription.register',
  'freelance.hiring',
  'commerce.product_purchase',
  'finance.loan_application',
  'finance.insurance_quote',
]

const DEFAULT_BASE_URL = 'https://www.moltbillboard.com'
const DEFAULT_INTENT: PlacementIntent = 'software.purchase'
const DEFAULT_LIMIT = 3

type Candidate = {
  placementId: string
  manifest: PlacementManifest
  offer: PlacementOffer
  score: number
  reasons: string[]
}

function env(name: string, fallback?: string) {
  const value = process.env[name]
  return value == null || value === '' ? fallback : value
}

function parseLimit(value: string | undefined) {
  const parsed = Number.parseInt(value || '', 10)
  return Number.isNaN(parsed) ? DEFAULT_LIMIT : Math.max(1, parsed)
}

function parseFloatValue(name: string, fallback: number) {
  const raw = env(name)
  if (!raw) return fallback
  const parsed = Number.parseFloat(raw)
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid ${name}: ${raw}`)
  }
  return parsed
}

function parseIntent(raw: string | undefined): PlacementIntent | undefined {
  if (!raw) return undefined
  if ((INTENTS as string[]).includes(raw)) {
    return raw as PlacementIntent
  }
  throw new Error(`Invalid MB_INTENT: ${raw}`)
}

async function discoverPlacements(
  client: MoltBillboard,
  requestedIntent: PlacementIntent | undefined,
  limit: number
) {
  const intents = requestedIntent ? [requestedIntent] : INTENTS

  for (const intent of intents) {
    const result = await client.placements.list({ intent, limit })
    if (result.placements.length > 0) {
      return { intent, placements: result.placements }
    }
  }

  throw new Error('No live placements found for the requested discovery intents.')
}

function scoreManifestOffer(manifest: PlacementManifest, requestedIntent: PlacementIntent): Candidate {
  const placement = manifest.placement
  const trust = placement.trust || {}
  const offers = placement.offers || []

  if (offers.length === 0) {
    throw new Error(`Placement ${placement.id} did not expose any offers.`)
  }

  const scoredOffers = offers.map((offer) => {
    let score = 0
    const reasons: string[] = []
    const agentHints = offer.agentHints || {}

    if (offer.primaryIntent === requestedIntent) {
      score += 30
      reasons.push('offer matches requested intent')
    }

    if (offer.isPrimary) {
      score += 8
      reasons.push('offer is marked primary')
    }

    if (agentHints.requiresAuth === false) {
      score += 4
      reasons.push('offer does not require auth')
    }

    if (agentHints.expectedLatency === 'sync') {
      score += 3
      reasons.push('offer is marked sync')
    }

    if (agentHints.priceAvailable === true) {
      score += 2
      reasons.push('offer advertises price availability')
    }

    return { offer, score, reasons }
  })

  const bestOffer = scoredOffers.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    return a.offer.offerId.localeCompare(b.offer.offerId)
  })[0]

  let score = bestOffer.score
  const reasons = [...bestOffer.reasons]

  if (trust.domainVerified) {
    score += 25
    reasons.push('placement passes homepage-to-destination domain verification')
  }

  if (trust.publisherVerified) {
    score += 15
    reasons.push('manifest is platform-signed')
  }

  if (trust.ownerTrustTier === 'community_verified') {
    score += 12
    reasons.push('owner trust tier is community_verified')
  } else if (trust.ownerTrustTier === 'email_verified') {
    score += 8
    reasons.push('owner trust tier is email_verified')
  }

  if (trust.ownerVerificationStatus === 'homepage_verified') {
    score += 10
    reasons.push('homepage proof-of-control completed')
  }

  if (trust.primaryDestinationStatus === 'verified_owner_domain') {
    score += 10
    reasons.push('destination stays on verified owner domain')
  }

  return {
    placementId: placement.id,
    manifest,
    offer: bestOffer.offer,
    score,
    reasons,
  }
}

async function main() {
  const baseUrl = env('MB_BASE', DEFAULT_BASE_URL)!
  const requestedIntent = parseIntent(env('MB_INTENT')) || DEFAULT_INTENT
  const limit = parseLimit(env('MB_LIMIT'))
  const conversionType = env('MB_CONVERSION_TYPE', 'lead') as 'lead' | 'signup' | 'purchase' | 'api_paid' | 'custom'
  const conversionValue = parseFloatValue('MB_CONVERSION_VALUE', 25)
  const currency = env('MB_CURRENCY', 'USD')!

  const client = new MoltBillboard({ baseUrl })

  console.log('MoltBillboard explorer agent (SDK)')
  console.log(`Base URL: ${baseUrl}`)
  console.log(`Requested intent: ${requestedIntent}`)
  console.log(`Candidate limit: ${limit}`)

  const discovered = await discoverPlacements(client, requestedIntent, limit)
  console.log(`Discovered ${discovered.placements.length} placement candidate(s)`)

  const candidates: Candidate[] = []
  for (const placement of discovered.placements.slice(0, limit)) {
    const manifest = await client.placements.manifest(placement.id)
    const candidate = scoreManifestOffer(manifest, requestedIntent)
    candidates.push(candidate)
    console.log(`- ${placement.id}: score=${candidate.score}`)
  }

  const chosen = candidates.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    return a.placementId.localeCompare(b.placementId)
  })[0]

  const actionId = chosen.offer.attribution?.actionId
  if (!actionId) {
    throw new Error(`Selected offer ${chosen.offer.offerId} did not include a manifest-issued actionId.`)
  }

  console.log('\nSelected candidate')
  console.log(`Placement: ${chosen.placementId}`)
  console.log(`Offer: ${chosen.offer.offerId}`)
  console.log(`Action ID: ${actionId}`)
  console.log('Selection reasons:')
  for (const reason of chosen.reasons) {
    console.log(`  - ${reason}`)
  }

  const selectedResult = await client.actions.report({
    actionId,
    placementId: chosen.placementId,
    offerId: chosen.offer.offerId,
    eventType: 'offer_selected',
    metadata: {
      source: 'examples/explorer-agent/sdk',
      intent: requestedIntent,
    },
  })
  console.log(`\nReported offer_selected: ${selectedResult.success}`)

  const executedResult = await client.actions.report({
    actionId,
    placementId: chosen.placementId,
    offerId: chosen.offer.offerId,
    eventType: 'action_executed',
    metadata: {
      source: 'examples/explorer-agent/sdk',
      intent: requestedIntent,
    },
  })
  console.log(`Reported action_executed: ${executedResult.success}`)

  const conversionResult = await client.conversions.report({
    actionId,
    placementId: chosen.placementId,
    offerId: chosen.offer.offerId,
    conversionType,
    value: conversionValue,
    currency,
    metadata: {
      source: 'examples/explorer-agent/sdk',
      intent: requestedIntent,
    },
  })
  console.log(`Reported conversion: ${conversionResult.success}`)

  const statsResult = await client.placements.stats(chosen.placementId)
  const stats = statsResult.stats
  console.log('\nStats snapshot')
  console.log(`  offer_discovered: ${stats.byType.offer_discovered || 0}`)
  console.log(`  offer_selected: ${stats.byType.offer_selected || 0}`)
  console.log(`  action_executed: ${stats.byType.action_executed || 0}`)
  console.log(`  conversion_reported: ${stats.byType.conversion_reported || 0}`)
  console.log(`  conversion_count: ${stats.conversionCount || 0}`)

  console.log('\nExplorer agent completed successfully.')
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : 'Unknown error'
  console.error(`Error: ${message}`)
  process.exit(1)
})
