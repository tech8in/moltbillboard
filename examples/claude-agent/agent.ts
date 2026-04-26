type AnthropicContentBlock =
  | {
      type: 'text'
      text: string
    }
  | {
      type: 'mcp_tool_use'
      id: string
      name: string
      server_name: string
      input: unknown
    }
  | {
      type: 'mcp_tool_result'
      tool_use_id: string
      is_error: boolean
      content: unknown
    }
  | {
      type: string
      [key: string]: unknown
    }

type AnthropicMessageResponse = {
  id: string
  model: string
  role: string
  stop_reason: string | null
  content: AnthropicContentBlock[]
}

const DEFAULT_MODEL = 'claude-sonnet-4-20250514'
const DEFAULT_INTENT = 'software.purchase'
const DEFAULT_LIMIT = 3
const DEFAULT_CONVERSION_TYPE = 'lead'
const DEFAULT_CONVERSION_VALUE = 25
const DEFAULT_CURRENCY = 'USD'

function env(name: string, fallback?: string) {
  const value = process.env[name]
  return value == null || value === '' ? fallback : value
}

function requiredEnv(name: string) {
  const value = env(name)
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`)
  }
  return value
}

function parseBoolean(value: string | undefined, fallback = false) {
  if (value == null) return fallback
  const normalized = value.trim().toLowerCase()
  if (normalized === 'true') return true
  if (normalized === 'false') return false
  throw new Error(`Invalid boolean value: ${value}`)
}

function parseInteger(value: string | undefined, fallback: number) {
  if (!value) return fallback
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`Invalid integer value: ${value}`)
  }
  return parsed
}

function parseFloatValue(value: string | undefined, fallback: number) {
  if (!value) return fallback
  const parsed = Number.parseFloat(value)
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid float value: ${value}`)
  }
  return parsed
}

function buildPrompt(options: {
  intent: string
  limit: number
  allowMutations: boolean
  conversionType: string
  conversionValue: number
  currency: string
}) {
  const discoveryInstructions = [
    `Use the MoltBillboard MCP server to discover placements for the exact intent "${options.intent}" with limit ${options.limit}.`,
    'Call browse_placements first.',
    'Pick the strongest candidate based on the manifest trust and offer data, then call fetch_manifest for that placement.',
    'Return strict JSON only.',
    'Use this schema:',
    '{"requestedIntent":"string","placements":[{"id":"string","legacyId":"string|null","aliases":["string"],"owner":"string|null","signals":["string"]}],"selectedPlacement":{"id":"string","reason":"string"},"topOffer":{"offerId":"string|null","primaryIntent":"string|null","actionId":"string|null","requiresAuth":"boolean|null","expectedLatency":"string|null"},"trust":{"publisherVerified":"boolean|null","domainVerified":"boolean|null","ownerTrustTier":"string|null","ownerHomepageVerified":"boolean|null","primaryDestinationStatus":"string|null"},"notes":["string"]}',
    'Do not invent fields. Use null when a field is absent.',
  ]

  if (!options.allowMutations) {
    discoveryInstructions.push('Do not call report_action or report_conversion.')
    return discoveryInstructions.join('\n')
  }

  discoveryInstructions.push(
    `If the selected offer includes an actionId, call report_action twice with eventType "offer_selected" and "action_executed", then call report_conversion with conversionType "${options.conversionType}", value ${options.conversionValue}, currency "${options.currency}", and metadata.source "examples/claude-agent".`,
    'Include an "attribution" object in the JSON response with keys "offerSelected", "actionExecuted", and "conversionReported". Use null when the actionId is missing.'
  )

  return discoveryInstructions.join('\n')
}

function extractText(blocks: AnthropicContentBlock[]) {
  return blocks
    .filter((block): block is Extract<AnthropicContentBlock, { type: 'text' }> => block.type === 'text')
    .map((block) => block.text)
    .join('\n')
    .trim()
}

function listToolCalls(blocks: AnthropicContentBlock[]) {
  return blocks.filter(
    (block): block is Extract<AnthropicContentBlock, { type: 'mcp_tool_use' }> => block.type === 'mcp_tool_use'
  )
}

async function callAnthropic(body: Record<string, unknown>, apiKey: string) {
  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-beta': 'mcp-client-2025-04-04',
    },
    body: JSON.stringify(body),
  })

  const raw = await response.text()
  if (!response.ok) {
    throw new Error(`Anthropic API error (${response.status}): ${raw}`)
  }

  return JSON.parse(raw) as AnthropicMessageResponse
}

async function main() {
  const apiKey = requiredEnv('ANTHROPIC_API_KEY')
  const mcpUrl = requiredEnv('MB_MCP_URL')
  const mcpAuthToken = env('MB_MCP_AUTH_TOKEN')
  const model = env('ANTHROPIC_MODEL', DEFAULT_MODEL)!
  const intent = env('MB_INTENT', DEFAULT_INTENT)!
  const limit = parseInteger(env('MB_LIMIT'), DEFAULT_LIMIT)
  const allowMutations = parseBoolean(env('MB_ENABLE_ATTRIBUTION_MUTATIONS'), false)
  const conversionType = env('MB_CONVERSION_TYPE', DEFAULT_CONVERSION_TYPE)!
  const conversionValue = parseFloatValue(env('MB_CONVERSION_VALUE'), DEFAULT_CONVERSION_VALUE)
  const currency = env('MB_CURRENCY', DEFAULT_CURRENCY)!

  const allowedTools = allowMutations
    ? ['browse_placements', 'fetch_manifest', 'report_action', 'report_conversion']
    : ['browse_placements', 'fetch_manifest']

  const prompt = buildPrompt({
    intent,
    limit,
    allowMutations,
    conversionType,
    conversionValue,
    currency,
  })

  const message = await callAnthropic(
    {
      model,
      max_tokens: 1400,
      messages: [
        {
          role: 'user',
          content: prompt,
        },
      ],
      mcp_servers: [
        {
          type: 'url',
          url: mcpUrl,
          name: 'moltbillboard',
          ...(mcpAuthToken ? { authorization_token: mcpAuthToken } : {}),
          tool_configuration: {
            enabled: true,
            allowed_tools: allowedTools,
          },
        },
      ],
    },
    apiKey
  )

  console.log('Claude MCP demo')
  console.log(`Model: ${message.model}`)
  console.log(`Stop reason: ${message.stop_reason || 'unknown'}`)
  console.log(`Intent: ${intent}`)
  console.log(`MCP URL: ${mcpUrl}`)
  console.log(`Allowed tools: ${allowedTools.join(', ')}`)

  const toolCalls = listToolCalls(message.content)
  if (toolCalls.length > 0) {
    console.log('\nTool calls')
    for (const toolCall of toolCalls) {
      console.log(`- ${toolCall.server_name}.${toolCall.name}`)
    }
  }

  const text = extractText(message.content)
  console.log('\nClaude response')
  if (text) {
    console.log(text)
  } else {
    console.log(JSON.stringify(message.content, null, 2))
  }
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : 'Unknown error'
  console.error(`Error: ${message}`)
  process.exitCode = 1
})
