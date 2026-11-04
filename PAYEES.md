# Payees in the Quarter feed

Feed version 4, issued 2026-11-03. 39 payees, all `known`, with 183 listed prices. 0 are `caution`.

A payee entry tells a gateway who an agent is about to pay and what that payee usually charges. `FORMAT.md` has the format.

- `known`: listed in a public directory. Quarter has not vetted it, and a listing can be faked. Nothing asks because a payee is known.
- `caution`: a public report says paying it has gone wrong. A person is asked first.
- A payment of more than ten times a listed price asks a person, for any payee.
- A payee nobody has listed is not suspect. Nothing asks because of that.

## Where the known payees come from

Coinbase's x402 Bazaar, the public discovery list of its x402 facilitator: https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources. It needs no key (https://docs.cdp.coinbase.com/x402/bazaar). On 2026-11-03 it listed 112,238 resources. The seed takes the first 1,000 it returned, keeps those paid by 25 or more distinct payers in the last 30 days by the list's own count, and keeps their USDC prices on networks Quarter's x402 client pays on (Base, Polygon, Arbitrum, Ethereum, Avalanche, Solana) with the `exact` scheme. Each listed amount becomes `max_usd` for that resource. A payee is one service name, with every address it is paid at. Names are as the sellers list them; Quarter has not checked who runs each one.

Payer counts are the list's own and can be inflated. That is why `known` never lets anything through that would otherwise ask.

## Why there are no caution entries yet

A `caution` entry needs a public report that names the payee's address or host. None was found for an x402 payee. The October 2025 402bridge loss came from a leaked contract key, not from paying a bad payee (https://crypto.news/402bridge-hack-leads-to-over-200-users-drained-of-usdc/). Reports from other companies stay out of the feed until a report can be disputed.

## The payees

- 402rates.com (`x402.402rates-com`): 3 addresses on Arbitrum, Base, Polygon, 1 price.
- agentbit.app (`x402.agentbit-app`): 4 addresses on Arbitrum, Base, Polygon, Solana, 1 price.
- api.loyalspark.online (`x402.api-loyalspark-online`): 1 address on Base, 7 prices.
- api.onesource.io (`x402.api-onesource-io`): 1 address on Base, 64 prices.
- api.printmoneylab.com (`x402.api-printmoneylab-com`): 3 addresses on Base, Polygon, Solana, 1 price.
- api.run402.com (`x402.api-run402-com`): 1 address on Base, 1 price.
- Apify (`x402.apify`): 2 addresses on Base, Solana, 1 price.
- ApiToll Crypto Prices (`x402.apitoll-crypto-prices`): 2 addresses on Base, Solana, 1 price.
- ApiToll SEC Filings (`x402.apitoll-sec-filings`): 2 addresses on Base, Solana, 1 price.
- AX1 Console (`x402.ax1-console`): 1 address on Base, 1 price.
- Bitrefill (`x402.bitrefill`): 4 addresses on Arbitrum, Base, Polygon, Solana, 1 price.
- BlockRun.AI (`x402.blockrun-ai`): 2 addresses on Base, 9 prices.
- Chit402 (`x402.chit402`): 2 addresses on Base, Solana, 1 price.
- cloud.trycorpus.ai (`x402.cloud-trycorpus-ai`): 10 addresses on Arbitrum, Avalanche, Base, Ethereum, Polygon, 18 prices.
- Coil Crypto Gate (`x402.coil-crypto-gate`): 2 addresses on Base, Solana, 1 price.
- CoinGecko (`x402.coingecko`): 3 addresses on Base, Polygon, Solana, 1 price.
- Exa (`x402.exa`): 3 addresses on Base, Solana, 2 prices.
- glim.sh (`x402.glim-sh`): 2 addresses on Base, Solana, 1 price.
- hyperextend (`x402.hyperextend`): 1 address on Base, 1 price.
- keyring-agent.blockchhub.link (`x402.keyring-agent-blockchhub-link`): 1 address on Base, 2 prices.
- Laso Finance (`x402.laso-finance`): 2 addresses on Base, Solana, 2 prices.
- Minifetch Technical SEO API (`x402.minifetch-technical-seo-api`): 2 addresses on Base, Solana, 1 price.
- Nansen (`x402.nansen`): 2 addresses on Base, Solana, 10 prices.
- Oblique Markets (`x402.oblique-markets`): 2 addresses on Base, Solana, 4 prices.
- Otto AI (`x402.otto-ai`): 2 addresses on Base, Solana, 5 prices.
- Pocket Network (`x402.pocket-network`): 1 address on Base, 4 prices.
- Quartermaster Gas Prices (`x402.quartermaster-gas-prices`): 2 addresses on Base, Solana, 1 price.
- StableEnrich (`x402.stableenrich`): 2 addresses on Base, Solana, 5 prices.
- StableUpload (`x402.stableupload`): 2 addresses on Base, Solana, 1 price.
- TenPrint (`x402.tenprint`): 2 addresses on Base, Solana, 2 prices.
- tick.hugen.tokyo (`x402.tick-hugen-tokyo`): 2 addresses on Base, Solana, 3 prices.
- Twitter/X API (`x402.twitter-x-api`): 4 addresses on Arbitrum, Base, Polygon, Solana, 1 price.
- Vibe Springs (`x402.vibe-springs`): 1 address on Base, 1 price.
- Web Search, News & Page Reader (`x402.web-search-news-page-reader`): 4 addresses on Arbitrum, Base, Polygon, Solana, 1 price.
- win.oneshotagent.com (`x402.win-oneshotagent-com`): 1 address on Base, 2 prices.
- X Pay (`x402.x-pay`): 1 address on Base, 13 prices.
- x402 Weather API (`x402.x402-weather-api`): 4 addresses on Arbitrum, Base, Polygon, Solana, 1 price.
- x402.asterpay.io (`x402.x402-asterpay-io`): 4 addresses on Arbitrum, Base, Ethereum, Polygon, 9 prices.
- x402.twit.sh (`x402.x402-twit-sh`): 1 address on Base, 1 price.
