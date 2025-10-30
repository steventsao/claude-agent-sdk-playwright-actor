#!/usr/bin/env python3
"""
Apify Actor: Brand Guideline Creator

This actor generates comprehensive brand guidelines using Claude Agent SDK.
It analyzes brands and creates detailed brand guideline documents.
"""

import asyncio
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict

from apify import Actor
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PLAYWRIGHT_ARTIFACT_DIR = Path(
    os.getenv("PLAYWRIGHT_ARTIFACT_DIR", "/usr/src/app/.playwright-mcp")
)
WORKSPACE_OUTPUT_ROOT = Path(
    os.getenv("ACTOR_OUTPUT_ROOT", "/usr/src/app")
)
WORKSPACE_ALLOWED_SUFFIXES = {
    ".html",
    ".htm",
    ".md",
    ".markdown",
    ".txt",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".zip",
}
WORKSPACE_EXCLUDED_DIRS = {
    ".apify_storage",
    ".cache",
    ".config",
    ".git",
    ".local",
    ".npm",
    ".playwright-mcp",
    ".venv",
    "__pycache__",
    "node_modules",
    "src",
    "venv",
}


def _list_artifact_files(directory: Path) -> Dict[Path, int]:
    if not directory.exists():
        return {}

    snapshot: Dict[Path, int] = {}
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            snapshot[path] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return snapshot


def _list_workspace_files(
    base_dir: Path,
) -> Dict[Path, int]:
    if not base_dir.exists():
        return {}

    snapshot: Dict[Path, int] = {}
    for root, dirs, files in os.walk(base_dir):
        root_path = Path(root)

        relative_parts = root_path.relative_to(base_dir).parts if root_path != base_dir else ()
        if any(part in WORKSPACE_EXCLUDED_DIRS for part in relative_parts):
            dirs[:] = []
            continue

        dirs[:] = [
            d
            for d in dirs
            if d not in WORKSPACE_EXCLUDED_DIRS
        ]

        for name in files:
            path = root_path / name
            if path.suffix.lower() in WORKSPACE_ALLOWED_SUFFIXES:
                try:
                    snapshot[path] = path.stat().st_mtime_ns
                except FileNotFoundError:
                    continue

    return snapshot


def _diff_snapshots(
    before: Dict[Path, int],
    after: Dict[Path, int],
) -> set[Path]:
    changed: set[Path] = set()
    for path, mtime in after.items():
        previous = before.get(path)
        if previous is None or previous != mtime:
            changed.add(path)
    return changed


async def _store_files(
    base_dir: Path,
    files: set[Path],
    category: str,
) -> list[Dict[str, str]]:
    if not files:
        return []

    store = await Actor.open_key_value_store()
    env_info = Actor.get_env()
    run_id = getattr(env_info, "actor_run_id", None)
    if not run_id and isinstance(env_info, dict):
        run_id = env_info.get("actorRunId") or env_info.get("actor_run_id")
    run_id = run_id or "run"

    stored = []
    for path in sorted(files):
        try:
            relative = path.relative_to(base_dir)
            clean_name = str(relative).replace(os.sep, "_")
        except ValueError:
            clean_name = path.name

        key_parts = [run_id, category, clean_name]
        key = "_".join(part for part in key_parts if part)
        content_type, _ = mimetypes.guess_type(path.name)
        data = path.read_bytes()

        await store.set_value(
            key,
            data,
            content_type=content_type or "application/octet-stream",
        )

        Actor.log.info(f"Stored file '{path}' as key '{key}' in default KV store")
        stored.append({"key": key, "path": str(path), "category": category})

    return stored


async def run_claude_task(task: str, url: str | None = None, api_key: str | None = None) -> Dict[str, Any]:
    """
    Run a Claude task with Playwright MCP.

    Args:
        task: The task description for Claude
        url: Optional starting URL
        api_key: Anthropic API key

    Returns:
        Dict with task result and metadata
    """
    # Set API key
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment or input")

    # Configure Playwright MCP server
    playwright_mcp = {
        "command": "npx",
        "args": [
            "@playwright/mcp@latest",
            "--browser", "chromium",
            "--headless",
            "--no-sandbox"
        ]
    }

    # Configure Claude SDK options
    options = ClaudeAgentOptions(
        model="haiku",
        mcp_servers={"playwright": playwright_mcp},
        permission_mode="bypassPermissions",  # Skip all permission checks for automation
    )

    # Build the prompt
    prompt = task
    if url:
        prompt = f"Navigate to {url} and then: {task}"

    existing_artifacts = _list_artifact_files(PLAYWRIGHT_ARTIFACT_DIR)
    existing_workspace_files = _list_workspace_files(WORKSPACE_OUTPUT_ROOT)

    Actor.log.info(f"Starting Claude task: {prompt}")

    # Run the task
    responses = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)

        # Collect all responses
        async for message in client.receive_response():
            Actor.log.info(f"Response: {message}")
            responses.append(str(message))

    Actor.log.info("Task completed")

    new_artifacts_snapshot = _list_artifact_files(PLAYWRIGHT_ARTIFACT_DIR)
    new_workspace_snapshot = _list_workspace_files(WORKSPACE_OUTPUT_ROOT)

    new_artifacts = _diff_snapshots(existing_artifacts, new_artifacts_snapshot)
    new_workspace_files = _diff_snapshots(existing_workspace_files, new_workspace_snapshot)

    stored_artifacts = await _store_files(PLAYWRIGHT_ARTIFACT_DIR, new_artifacts, category="playwright")
    stored_outputs = await _store_files(WORKSPACE_OUTPUT_ROOT, new_workspace_files, category="workspace")
    stored_files = stored_artifacts + stored_outputs

    return {
        "success": True,
        "task": task,
        "url": url,
        "responses": responses,
        "final_response": responses[-1] if responses else None,
        "artifacts": stored_artifacts,
        "output_files": stored_outputs,
        "stored_files": stored_files,
    }


async def generate_llms_txt_from_kv_store(
    kv_store_id: str,
    domain: str,
    api_key: str | None = None
) -> str:
    """
    Read files from Actor 1's KV store and generate llms.txt using Claude Agent SDK.

    Args:
        kv_store_id: KV store ID from Actor 1
        domain: Brand domain
        api_key: Anthropic API key for Claude

    Returns:
        Generated llms.txt content
    """
    import json

    Actor.log.info(f"Opening KV store: {kv_store_id}")

    # Set API key
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment or input")

    # Open Actor 1's KV store with force_cloud=True for remote access
    kv_store = await Actor.open_key_value_store(id=kv_store_id, force_cloud=True)

    # List all files in the KV store using Apify SDK
    Actor.log.info("Listing KV store files...")

    # Collect all keys first
    keys = []
    async for key_metadata in kv_store.iterate_keys():
        keys.append(key_metadata)

    Actor.log.info(f"Found {len(keys)} files in KV store")

    # Download key files we need
    files_content = {}
    for key_metadata in keys:
        key_name = key_metadata.key
        Actor.log.info(f"Reading file: {key_name}")

        try:
            # Get file content
            record = await kv_store.get_value(key_name)

            if record:
                # Store as string if it's text, otherwise skip
                if isinstance(record, (str, dict)):
                    # Convert dict to formatted JSON string
                    if isinstance(record, dict):
                        files_content[key_name] = json.dumps(record, indent=2)
                    else:
                        files_content[key_name] = record
                    Actor.log.info(f"  ✓ Loaded {key_name}")
                else:
                    Actor.log.info(f"  ⊘ Skipped binary file {key_name}")
        except Exception as e:
            Actor.log.warning(f"  ✗ Failed to read {key_name}: {e}")

    if not files_content:
        Actor.log.warning("No files found in KV store, generating basic template")
        return f"""# {domain} Design System

> Brand design guidelines and style tokens

## Overview

This is the design system for {domain}.

Note: No design files were available for analysis.

---

Generated by Apify Brand Guideline Creator
"""

    # Generate llms.txt using Claude Agent SDK
    Actor.log.info(f"Generating llms.txt for {domain} with {len(files_content)} files using Claude Agent SDK")

    # Build comprehensive prompt with example format
    files_list = "\n".join(f"**{k}**:\n{v[:800] if len(v) > 800 else v}\n" for k, v in list(files_content.items())[:10])

    prompt = f"""SYSTEM CONTEXT: You are running in an automated VM environment. DO NOT ask questions or wait for user input. Work autonomously until the task is complete.

TASK: Generate an llms.txt file for {domain} following the official llms.txt specification from llmstxt.org.

**Files from KV store ({len(files_content)} total)**:
{files_list}

**OFFICIAL llms.txt FORMAT SPECIFICATION**:

The llms.txt file MUST follow this structure in exact order:

1. **H1 heading** (required): Brand/project name
2. **Blockquote** (required): Concise summary with key brand information
3. **Detailed content sections** (optional): Markdown sections explaining brand guidelines WITHOUT H2 headings initially
4. **H2 "Optional" section** (optional): Secondary information that can be omitted for shorter context

**REQUIRED OUTPUT FORMAT**:
```markdown
# {{Brand Name}}

> Concise one-line summary of the brand's design identity and purpose

This is the design system and brand guidelines for {{domain}}. [2-3 clear sentences about the brand, its visual identity, and design principles. Use concise, clear language without jargon.]

**Brand Overview**: [Brief description of brand personality and positioning]

**Design Principles**: [Core design values and approach]

**Color Palette**:
- Primary: #XXXXXX (RGB: X, X, X) - [Usage and meaning]
- Secondary: #XXXXXX (RGB: X, X, X) - [Usage and meaning]
- Accent: #XXXXXX (RGB: X, X, X) - [Usage and meaning]
[List ALL colors found in files with actual hex values]

**Typography**:
- Primary: [Font Family], weights: [list]
- Secondary: [Font Family], weights: [list]
- Heading styles: [specifications]
- Body styles: [specifications]

**Spacing & Layout**: [Spacing tokens, grid system, breakpoints]

**Component Patterns**: [Button styles, cards, forms, navigation patterns]

**Design Tokens**: [CSS variables, border radius, shadows, animations]

## Optional

**Technical Implementation**: [Framework details, browser support, build tools]

**Additional Resources**: [Links to detailed documentation if available]
```

**CRITICAL INSTRUCTIONS**:
1. Follow the llms.txt.org specification EXACTLY - H1, blockquote, then content
2. Use concise, clear language throughout
3. Extract ACTUAL values from files - no placeholders like #XXXXXX
4. The blockquote MUST be a single-line summary
5. Main content should NOT use H2 headings except for "Optional" section
6. Use bold markdown (**text**) and lists for structure instead of headings
7. Include brief, informative descriptions with every resource
8. Test that an LLM could understand this without ambiguity
9. Use the Write tool to create /usr/src/app/llms.txt
10. DO NOT include meta-commentary, system messages, or tool outputs in the file

Start working now. Analyze the files and write llms.txt."""

    try:
        # Configure Claude SDK options with custom system prompt
        options = ClaudeAgentOptions(
            model="sonnet",
            permission_mode="bypassPermissions",
            custom_system_prompt_suffix="""

CRITICAL INSTRUCTIONS FOR THIS SESSION:
- You are running in an automated environment with no human interaction
- DO NOT ask clarifying questions or present options
- Work autonomously with the information provided
- When writing llms.txt, include ONLY the brand guideline markdown content
- DO NOT include system messages, tool outputs, or meta-commentary in the file
- Extract actual values from the files provided - no placeholders
- Complete the task fully before ending the session"""
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)

            # Collect all responses (for logging)
            async for message in client.receive_response():
                Actor.log.info(f"Claude response: {str(message)[:200]}...")

        # Claude should have written llms.txt using the Write tool
        # Check if the file was created
        llms_txt_path = Path("/usr/src/app/llms.txt")

        if llms_txt_path.exists():
            Actor.log.info("Found llms.txt file generated by Claude")
            llms_txt = llms_txt_path.read_text()

            # Verify it doesn't contain system messages or tool outputs
            if "SystemMessage" in llms_txt or "AssistantMessage" in llms_txt or "ResultMessage" in llms_txt:
                Actor.log.warning("llms.txt contains system messages, attempting to clean...")
                # Try to extract just the markdown content between common delimiters
                if "```markdown" in llms_txt:
                    # Extract content between markdown code blocks
                    import re
                    match = re.search(r'```markdown\s*(.*?)\s*```', llms_txt, re.DOTALL)
                    if match:
                        llms_txt = match.group(1).strip()
        else:
            Actor.log.warning("llms.txt not found, using fallback template")
            llms_txt = f"""# {domain} Design System

> Brand design guidelines and style tokens

## Overview

This is the design system for {domain}.

## Files Analyzed

{chr(10).join(f'- {k}' for k in files_content.keys())}

Note: Automated analysis encountered an issue. Please review manually.
"""

        # Add generation footer
        llms_txt += f"""

---

Generated by Apify Brand Guideline Creator
Files analyzed: {len(files_content)}
Source: {domain}
"""

        Actor.log.info("Generated llms.txt using Claude Agent SDK")
        return llms_txt

    except Exception as e:
        Actor.log.exception(f"Failed to generate llms.txt with Claude: {e}")
        # Fallback to basic template
        return f"""# {domain} Design System

> Brand design guidelines and style tokens

## Overview

This is the design system for {domain}.

## Files Analyzed

{chr(10).join(f'- {k}' for k in files_content.keys())}

---

Generated by Apify Brand Guideline Creator
Files analyzed: {len(files_content)}
Note: Error occurred during AI analysis - {str(e)}
"""


async def submit_to_flask(
    domain: str,
    llms_txt: str,
    flask_api_url: str,
    flask_api_secret: str
) -> Dict[str, Any]:
    """
    Submit llms.txt to Flask API privileged endpoint.

    Args:
        domain: Brand domain
        llms_txt: Generated llms.txt content
        flask_api_url: Flask base URL
        flask_api_secret: API authentication secret

    Returns:
        API response data
    """
    import aiohttp

    url = f"{flask_api_url.rstrip('/')}/api/submit-llms-txt"

    Actor.log.info(f"Submitting llms.txt to {url}")

    headers = {
        "Content-Type": "application/json",
        "X-Actor-Secret": flask_api_secret
    }

    payload = {
        "domain": domain,
        "llms_txt": llms_txt
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            response_data = await response.json()

            if response.status == 200:
                Actor.log.info(f"✅ Successfully submitted llms.txt for {domain}")
                return {"success": True, "response": response_data}
            else:
                Actor.log.error(f"❌ Failed to submit: {response.status} - {response_data}")
                return {"success": False, "error": response_data, "status": response.status}


async def main() -> None:
    """Main actor entry point."""
    async with Actor:
        Actor.log.info("Brand Guideline Creator Actor starting...")

        # Get input
        actor_input = await Actor.get_input() or {}

        # Handle both webhook mode (defaultKeyValueStoreId) and direct mode (kvStoreId)
        kv_store_id = actor_input.get("defaultKeyValueStoreId") or actor_input.get("kvStoreId")
        domain = actor_input.get("domain")

        flask_api_url = actor_input.get("flaskApiUrl", "https://styleguide.fyi")
        flask_api_secret = actor_input.get("flaskApiSecret")
        api_key = actor_input.get("anthropicApiKey")
        output_dataset_id = actor_input.get("outputDatasetId")

        # Legacy support for old task-based input
        task = actor_input.get("task")
        url = actor_input.get("url")

        Actor.log.info(f"Input received - kvStoreId: {kv_store_id}, domain: {domain}, task: {task}")

        # If we have kvStoreId but no domain, fetch INPUT from KV store
        if kv_store_id and not domain:
            Actor.log.info(f"Fetching INPUT from KV store {kv_store_id} to get domain and credentials")
            try:
                kv_store = await Actor.open_key_value_store(id=kv_store_id, force_cloud=True)
                input_record = await kv_store.get_value("INPUT")

                if input_record:
                    domain = input_record.get("domain")

                    # Handle encrypted secrets from INPUT
                    # Check if secrets are ENCRYPTED_VALUE objects or plain strings
                    raw_flask_secret = input_record.get("flaskApiSecret")
                    raw_api_key = input_record.get("anthropicApiKey")

                    Actor.log.info(f"Raw flask_secret type: {type(raw_flask_secret)}, value: {raw_flask_secret}")
                    Actor.log.info(f"Raw api_key type: {type(raw_api_key)}, value: {raw_api_key}")

                    # Use secrets from INPUT if not provided directly
                    flask_api_secret = flask_api_secret or raw_flask_secret
                    api_key = api_key or raw_api_key

                    Actor.log.info(f"Retrieved from INPUT - domain: {domain}, has_flask_secret: {bool(flask_api_secret)}, has_api_key: {bool(api_key)}")
                else:
                    Actor.log.error("INPUT record not found in KV store")
                    await Actor.fail()
                    return
            except Exception as e:
                Actor.log.exception(f"Failed to fetch INPUT from KV store: {e}")
                await Actor.fail()
                return

        # Mode 1: New llms.txt generation from KV store (webhook-triggered)
        if kv_store_id and domain:
            Actor.log.info(f"Mode: Generate llms.txt from KV store {kv_store_id}")

            try:
                # Generate llms.txt from KV store files
                llms_txt = await generate_llms_txt_from_kv_store(kv_store_id, domain, api_key)

                # Submit to Flask API if credentials provided
                flask_result = None
                if flask_api_secret:
                    flask_result = await submit_to_flask(domain, llms_txt, flask_api_url, flask_api_secret)
                else:
                    Actor.log.warning("No flaskApiSecret provided, skipping Flask submission")

                result = {
                    "success": True,
                    "mode": "llms_txt_generation",
                    "domain": domain,
                    "kv_store_id": kv_store_id,
                    "llms_txt": llms_txt,
                    "flask_submission": flask_result
                }

                # Push to dataset
                if output_dataset_id:
                    await Actor.push_data(result, dataset_id=output_dataset_id)
                else:
                    await Actor.push_data(result)

                Actor.log.info("✅ llms.txt generation completed")

            except Exception as e:
                Actor.log.exception("llms.txt generation failed")
                await Actor.fail()
                return

        # Mode 2: Legacy task-based execution
        elif task:
            Actor.log.info("Mode: Legacy Claude task execution")

            try:
                # Run the task
                result = await run_claude_task(task, url, api_key)

                # Push to dataset
                if output_dataset_id:
                    await Actor.push_data(result, dataset_id=output_dataset_id)
                else:
                    await Actor.push_data(result)

                Actor.log.info("Results pushed to dataset")

            except Exception as e:
                Actor.log.exception("Task failed")
                await Actor.fail()

        else:
            Actor.log.error("Invalid input: Must provide either (kvStoreId + domain) or (task)")
            await Actor.fail()


if __name__ == "__main__":
    asyncio.run(main())
