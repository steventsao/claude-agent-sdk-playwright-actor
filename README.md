# Brand Guideline Creator Actor

Generate comprehensive brand guidelines using Claude Agent SDK. This Apify Actor analyzes brands and creates detailed brand guideline documents. See [example-prompt.md](./example-prompt.md) for reference.

## Usage

### Input Schema

```json
{
  "task": "Create brand guidelines for Nike based on their website",
  "url": "https://nike.com",
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
cd actor-brand-guideline-creator

# Install dependencies
pip install uv
uv sync

# Run locally
uv run python -m actor_brand_guideline_creator
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

- **Anthropic API key**: The actor fails fast if `ANTHROPIC_API_KEY` is missing. Set it in the actor input (`anthropicApiKey`) or as an environment variable.

## File Storage

- Generated brand guideline documents (`.md`, `.json`, `.pdf`, `.png`, etc.) are uploaded to the run's default key-value store. Reference the `output_files` or `stored_files` fields in the dataset output to retrieve them.
