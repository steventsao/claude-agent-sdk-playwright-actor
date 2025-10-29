# Extract Visual Design System from Website

## Task
Extract the visual design system from a given website, including semantic color tokens, typography (fonts and weights), and create a documented HTML showcase.

## Steps

### 1. Navigate & Inspect
- Navigate to the target website using Playwright
- Examine network requests to identify CSS files
- Take initial snapshot of the page structure

### 2. Extract Color Tokens
- Fetch the main CSS files from network requests
- Extract semantic color tokens:
  - Primary colors
  - Background colors
  - Accent colors
  - State colors (destructive, success, warning)
  - Look for CSS custom properties (--variable-name)
  - Extract hex codes, RGB, HSL values
- **Target: 3-5 main colors** that represent the brand

### 3. Extract Typography
- Identify font files loaded by the page (Google Fonts, local assets)
- Extract:
  - Font family names
  - Available weights (400, 500, 600, 700, etc.)
  - Font file paths/URLs
- Use browser evaluation to get computed font styles

### 4. Create Output HTML
Generate `output.html` with:
- **Color Palette Section**: Display color swatches with names and values
- **Typography Section**: Show font samples at different weights with pangram examples
- **Components Section**: Build reusable components using extracted tokens:
  - Buttons (primary, secondary, destructive)
  - Typography hierarchy (H1, H2, H3, body text)
  - Card components
  - Any other common UI patterns
- **Note**: Omit imagery components (placeholder grids, upload UI) - save for later

### 5. Verify Output
- Navigate to the generated output.html using Playwright
- Take a screenshot to verify the design system is correctly rendered
- Ensure fonts load properly from their sources

## Output Format

### output.html Structure
```
- Title & Introduction
- Color Palette Grid (cards with swatches + color codes)
- Typography Section (font samples at each weight)
- Components Showcase (reusable UI elements)
- NO imagery components or placeholder grids
```

### Key Requirements
- Use actual font files from the source (Google Fonts link or local paths)
- Display both hex codes and HSL/RGB values for colors
- Show pangram examples for each font weight
- Create interactive/hoverable components
- Maintain clean, readable layout

## Tools Used
- Given site url, Use Browserbase to navigate
- Evaluate via Browserbase console for CSS tokens and structure, NOT WebFetch
- When taking a screenshot, do not take full webpages long. Be concise, at most its laptop, mobile phone viewport so it does not exceed API buffer
- Unfortunately you cant check your work like output.html yet because you are in a sandbox without local browser so localhost wouldn't work, including browserbase. So don't get stuck trying.

## Success Criteria
- 3-5 main colors extracted with semantic names
- Font family identified with all available weights
- output.html renders correctly with actual fonts
- Components demonstrate the design system in action
- Save all your work

site: {{site_url}}
