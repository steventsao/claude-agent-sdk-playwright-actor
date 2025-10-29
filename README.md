# Claude SDK + Playwright Actor

Apify actor that combines Claude Agent SDK with Playwright MCP for AI-powered browser automation.

## Features

- **Claude Agent SDK**: Latest Claude models with agentic capabilities
- **Playwright MCP**: Browser automation via Model Context Protocol
- **Headless Browser**: Pre-installed Chromium for web scraping
- **Python 3.12**: Modern Python runtime
- **Apify Integration**: Seamless dataset storage and workflow integration

## Usage

### Input Schema

```json
{
  "task": "Navigate to example.com and extract the main heading",
  "url": "https://example.com",
  "anthropicApiKey": "sk-ant-...",
  "outputDatasetId": "optional-dataset-id"
}
```

### Required Fields

- `task` (string): Description of what Claude should do

### Optional Fields

- `url` (string): Starting URL to navigate to
- `anthropicApiKey` (string): Your Anthropic API key (or set `ANTHROPIC_API_KEY` env var)
- `outputDatasetId` (string): Specific dataset ID to push results to

## Development

### Local Setup

```bash
cd actor-claude-sdk-playwright

# Install dependencies
pip install uv
uv sync

# Run locally
uv run python -m actor_claude_sdk_playwright
```

### Building the Actor

```bash
apify build
```

### Testing

```bash
apify run -i input.json
```

## Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required)
- `APIFY_TOKEN`: Apify API token (set automatically in Apify platform)

## Gotchas

- **Cloudflare challenge pages**: Sites such as `chatgpt.com` may return a Cloudflare Turnstile challenge, which the Playwright MCP server cannot solve. Complete the challenge manually in a regular browser (and pass any required cookies/session data to the actor) before continuing, or pick an automation-friendly target.
- **Anthropic API key**: The actor fails fast if `ANTHROPIC_API_KEY` is missing. Set it in the actor input (`anthropicApiKey`) or as an environment variable.
- **Browser bundle location**: Chromium is preinstalled during the Docker build and stored under `/pw-browsers`. If you ever change `PLAYWRIGHT_BROWSERS_PATH`, update `.actor/Dockerfile` accordingly and rebuild with `apify push --force`.

## File Storage

- Playwright MCP artifacts under `.playwright-mcp` and newly created workspace documents (`.html`, `.md`, `.json`, `.png`, etc.) are uploaded to the run's default key-value store. Reference the `artifacts`, `output_files`, or `stored_files` fields in the dataset output to retrieve them.

## Template Comparison

This actor is equivalent to the E2B template `claude-sdk-playwright` but designed for the Apify platform:

**E2B Template Features:**
- Python 3.12 base image
- Node.js 24 for MCP
- Claude SDK + Playwright MCP
- Custom resource allocation

**Apify Actor Features:**
- Apify Python SDK integration
- Dataset storage built-in
- Input/output schema validation
- Platform monitoring and logging
- Workflow integration

## Examples

### Web Scraping

```json
{
  "task": "Find all product prices on the page and return them as a list",
  "url": "https://example-shop.com/products"
}
```

### Form Automation

```json
{
  "task": "Fill out the contact form with: name='John Doe', email='john@example.com', message='Test message', then submit"
}
```

### Data Extraction

```json
{
  "task": "Navigate to the documentation page and extract all API endpoint examples"
}
```

## License

Apache 2.0
