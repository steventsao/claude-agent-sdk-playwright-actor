FROM apify/actor-python-playwright:3.12

WORKDIR /usr/src/app

ENV PLAYWRIGHT_BROWSERS_PATH=/pw-browsers

# Install Node.js 24 for Playwright MCP and other tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git ripgrep sudo && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI and Playwright MCP globally
RUN mkdir -p "$PLAYWRIGHT_BROWSERS_PATH" && \
    npm install -g @anthropic-ai/claude-code@latest @playwright/mcp@latest && \
    npx --yes playwright install --with-deps chromium

# Copy Python dependencies
COPY pyproject.toml uv.lock ./

# Install Python dependencies with uv
RUN echo "Python version:" \
    && python --version \
    && echo "Node.js version:" \
    && node --version \
    && echo "Installing uv:" \
    && pip install --no-cache-dir uv \
    && echo "Installing Python dependencies:" \
    && uv sync --frozen --no-dev \
    && echo "All installed Python packages:" \
    && uv pip freeze

# Copy source code
COPY src ./src

# Ensure Playwright browser directory and app files are owned by runtime user
RUN chown -R myuser:myuser /usr/src/app /pw-browsers

USER myuser

CMD ["uv", "run", "--no-dev", "--frozen", "python3", "-m", "actor_claude_sdk_playwright"]
