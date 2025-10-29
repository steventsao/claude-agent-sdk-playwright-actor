#!/usr/bin/env python3
"""
Apify Actor: Claude SDK + Playwright MCP

This actor provides Claude Agent SDK with Playwright MCP for browser automation.
It can perform complex web tasks using AI-powered browser control.
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


async def main() -> None:
    """Main actor entry point."""
    async with Actor:
        Actor.log.info("Actor starting...")

        # Get input
        actor_input = await Actor.get_input() or {}
        task = actor_input.get("task")
        url = actor_input.get("url")
        api_key = actor_input.get("anthropicApiKey")
        output_dataset_id = actor_input.get("outputDatasetId")

        if not task:
            Actor.log.error("Input 'task' is required")
            await Actor.fail()
            return

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


if __name__ == "__main__":
    asyncio.run(main())
