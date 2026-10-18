---
name: job-post-scraper
description: This skill should be used when scraping a single job posting URL or processing a provided job description text into structured JSON. Trigger when users ask to "scrape a job post", "extract job from URL", "add job posting", "scrape this job", "process this job description", or want to convert a job posting into a structured JSON file.
version: 0.1.1
user-invocable: true
---

# Job Post Scraper

Scrape a single job posting URL (or use provided text) and save it as structured JSON with interactive review.

## Overview

This skill simplifies the workflow of processing a single job posting:

1.  **Input Collection**: User provides a URL (Job Post URL or Apply URL) and optionally the raw job description text.
2.  **Content Acquisition**:
    *   **If user provided text**: Use the provided content directly (skips browsing).
    *   **If only URL provided**: Use `agent-browser` to scrape the page.
3.  **Extraction**: Extract job data from the content and map to schema.
4.  **Review**: Present data for manual review/editing.
5.  **UID Generation**: Generate unique random UID (e.g., `jp_a8f2k9m4`).
6.  **Storage**: Save to the job-posts directory with pattern `<uid>.json`.

## Configuration

The skill supports flexible directory configuration through multiple sources:

### Configuration Priority (highest to lowest):

1. ask user where to store the final job post files

### Default Paths

If no configuration is provided, the skill uses these defaults (relative to project root):

-   Job Posts: `back/data/job-posts`
-   Organizations: `back/data/orgs`

The project root is auto-detected by finding `package.json`, `.git`, or `back` directory.

## Workflow

### 1. Get Job Input

Parse the command arguments or ask the user to provide inputs.
*   **Required**: A URL (this serves as the `url` or `apply_url`).
*   **Optional**: The job description content/text.

### 4. Obtain Job Content

Determine the source of the job description:

**Path A: User provided description text**
*   **SKIP** the `agent-browser` step.
*   Use the user's provided text as the source content.
*   Use the user's provided URL as the metadata link.

**Path B: User provided ONLY a URL**
*   Use the `agent-browser` skill to open the URL and extract page content:
    ```bash
    # Use agent-browser skill to open URL and get page content
    # The agent-browser will navigate and extract the page content
    ```


### 3. Extract Job Data

Extract job posting details from this page and return ONLY valid JSON following the example structure:

```json
{
  "meta": {
    "uid": "jp_a8f2k9m4",
    "is_deleted": false,
    "archived_at": null,
    "created_at": "2026-01-30T12:00:00.000Z",
    "updated_at": "2026-01-30T12:00:00.000Z",
    "published_at": "2026-01-30T12:00:00.000Z",
    "expires_at": null
  },
  "org": {
    "uid": "org_97afthhf"
  },
  "source": {
    "source_url": "https://www.source-url.com/job/uid123414234"
  },
  "parsed_airport_name": "JFK airport",
  "parsed_airport_iata": "JFK",
  "parsed_airport_icao": "<enter-icao-here>",
  "parsed_country_code": "US",
  "parsed_country_name": "United States of America",
  "parsed_state_code": "AZ",
  "parsed_state_name": "Arizona",
  "parsed_city_name": null,
  "job_category_uid": "jc_a1b2c3d4",
  "job_category_slug": "logistics-supply-chain",
  "apply_url": "https://www.external-website.com/apply?id=12345",
  "title": "Airport Aviation Screener ",
  "title_slug": "airport-aviation-screener",
  "work_mode": "on-site",
  "seniority": "mid",
  "contract_type": "full-time",
  "travel_required": true,
  "compensation_text": "Competitive salary based on experience",
  "description_markdown": "## About the Role.... GAT is seeking a highly motivated individual, a self-starter and team player, with a strong drive for results and continual improvement to join its team of aviation professionals. In joining our team, you will enjoy a competitive salary, great benefits, and a creative and energetic work environment.\n"
}

```

### 4. Display for Review

Show extracted data in a formatted, readable way.

### 7. User Review & Edit

Use AskUserQuestion to:

-   Confirm the data is correct
-   Allow editing if needed
-   Option to cancel and not save

### 8. Generate Unique UID

Generate a random unique identifier using cryptographic randomness:

Example UIDs:

-   `jp_a8f2k9m4`
-   `jp_x3n7p1q5`
-   `jp_k9m2v8h6`

The UID is 8 random alphanumeric characters with no special characters. This ensures:

-   No race conditions in concurrent processing
-   No directory scanning required
-   Globally unique identifiers
-   Collision resistance

### 9. Map to Schema

Create JSON file with full schema mapping.

### 10. Save Job Post

Save the file as `jp_a8f2k9m4.json` in the configured job-posts directory.

### 11. Success Message

Display confirmation with filename and UID

```
Job Post Saved Successfully
===========================
File: jp_a8f2k9m4.json
UID: jp_a8f2k9m4
Title: Supply Chain Manager
Organization: Airport Ground Services
Location: /path/to/back/data/job-posts/jp_a8f2k9m4.json
```
## Error Handling

-   **Invalid URL**: Show error and ask for valid URL (required even if text is provided).
-   **Scraping fails (when used)**: Log error, show what was retrieved, allow retry.
-   **Extraction incomplete**: Display what was extracted, ask user to fill missing fields.
-   **Network errors**: Retry up to 3 times with exponential backoff (only applicable if browsing).
-   **Invalid JSON**: Show raw content, ask for manual extraction.

## Implementation Details

### Utilities

Located in `skills/job-post-scraper/scripts/`:

**config.js**

-   `findProjectRoot()` - Auto-detect project root directory
-   `loadConfig()` - Load and merge configuration from env vars, config file, and defaults

**utils.js** (uses shared utilities from `${CLAUDE_PLUGIN_ROOT}/scripts/`)

-   `slugify(text)` - Convert text to URL-friendly slug (from slug-utils.js)
-   `createTitleSlug(title, orgName, location)` - Generate title_slug (from slug-utils.js)
-   `generateShortUID(prefix)` - Generate random UID with optional prefix (uses generate-uid.js)
-   `generateJobUID()` - Create random UID like `jp_a8f2k9m4`
-   `generateFilename(uid)` - Create filename from UID

**file-manager.js**
All functions use the config system internally:

-   `saveJobPost(jobData)` - Save with UID-based naming (UID must be in jobData.meta.uid)

## Agent-Browser Integration

The skill conditionally uses the `agent-browser` skill:

*   **Condition**: Used **ONLY** if the user does not provide the job description text manually.
*   **Function**:
    1.  Open the job posting URL
    2.  Wait for page to load
    3.  Extract the full page content
    4.  Return the content for LLM extraction