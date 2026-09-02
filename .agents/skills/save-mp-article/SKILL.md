---
name: save-mp-article
description: >-
  Download and convert WeChat Official Account (微信公众号) articles into cleanly formatted Markdown files in the local repository.
  Use this skill whenever the user provides a WeChat article URL (e.g., https://mp.weixin.qq.com/s/...), asks to save/archive a WeChat article, or asks to save the article currently open in the browser.
---

# WeChat MP Article Saver (微信公众号文章保存)

This skill automates downloading, extracting, and converting WeChat Official Account (`mp.weixin.qq.com`) articles into standardized Markdown files directly in the repository workspace.

## Workflow

### 1. Identify the Article URL

- **URL Provided in Prompt**: Use the URL directly.
- **"Save currently open article in browser"**:
  1. Call `chrome-devtools` MCP tool `list_pages`.
  2. Find the tab with URL matching `https://mp.weixin.qq.com/s/...`.
  3. Extract the URL from the tab metadata.

### 2. Run the Extractor Script

Execute the built-in helper script from the repository root:

```bash
python3 .agents/skills/save-mp-article/scripts/save_mp.py "<WECHAT_ARTICLE_URL>"
```

### 3. What the Script Does Automatically

1. **Fetches Content**: Pulls the full article HTML with correct desktop headers.
2. **Extracts Metadata**:
   - **Title**: From `#activity-name` / `.rich_media_title` / `og:title`.
   - **Publish Date**: Extracted from WeChat timestamp variable `ct` or `createDate` to form the `YYMMDD` prefix (e.g. `260902`).
3. **Parses & Formats Markdown**:
   - **Headings**: Converts `<h1>`..`<h6>` into `#`, `##`, etc.
   - **Bold Emphasis**: Retains inline bold styles (`<strong>`, `<b>`, and `<span style="font-weight: 500/600/700/bold">`) as `**text**`.
   - **Images**: High-resolution image CDN links preserved in standard Markdown `![Image](url)` syntax.
   - **Quotes & Code**: Preserves `<blockquote>`, code blocks, and list items.
   - **Clean Layout**: Eliminates redundant whitespace and WeChat hidden tracking tags while keeping paragraph spacing.
4. **Saves File**: Outputs to `<workspace_root>/<YYMMDD>-<Title>.md`.

### 4. Provide Verification & Feedback

After the script finishes, provide the user with:
- Clickable link to the generated `.md` file.
- Article Title and extracted date.
