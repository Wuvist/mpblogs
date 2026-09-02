#!/usr/bin/env python3
"""
WeChat Official Account (微信公众号) Article to Markdown Saver.
Converts WeChat articles to cleanly formatted Markdown preserving:
- Headings (#, ##, etc.)
- Bold & emphasis styles (including WeChat inline font-weight styles)
- Images with correct high-res URLs
- Code blocks, blockquotes, and lists
- Date prefix (YYMMDD-Title.md) based on publication date or current date
"""

import sys
import os
import re
import ssl
import json
import urllib.request
from datetime import datetime
from html import unescape
from html.parser import HTMLParser


class WeChatArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_author = False
        self.in_content = False
        
        self.title_parts = []
        self.author_parts = []
        self.content_parts = []
        
        self.tag_stack = []
        self.heading_level = 0
        self.bold_stack = 0
        self.italic_stack = 0
        self.in_pre = False
        self.in_code = False
        self.in_blockquote = False
        self.list_stack = []  # ('ul' | 'ol', item_counter)
        self.current_img_index = 0

    def is_bold_elem(self, tag, style):
        if tag in ('strong', 'b'):
            return True
        if style:
            # Check font-weight
            s = style.lower().replace(' ', '')
            if 'font-weight:500' in s or 'font-weight:600' in s or 'font-weight:700' in s or 'font-weight:bold' in s:
                return True
        return False

    def is_italic_elem(self, tag, style):
        if tag in ('em', 'i'):
            return True
        if style:
            s = style.lower().replace(' ', '')
            if 'font-style:italic' in s:
                return True
        return False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        style = attr_dict.get('style', '')
        tag_id = attr_dict.get('id', '')
        tag_cls = attr_dict.get('class', '')

        # Skip hidden elements
        if 'display:none' in style.lower().replace(' ', '') or 'display: none' in style:
            self.tag_stack.append((tag, attrs, False, False, True))
            return

        if tag_id == 'js_content' or 'rich_media_content' in tag_cls:
            self.in_content = True

        if not self.in_content:
            if tag_id == 'activity-name' or 'rich_media_title' in tag_cls:
                self.in_title = True
            elif tag_id == 'js_name' or 'rich_media_meta_nickname' in tag_cls:
                self.in_author = True
            self.tag_stack.append((tag, attrs, False, False, False))
            return

        is_bold = self.is_bold_elem(tag, style)
        is_italic = self.is_italic_elem(tag, style)

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.heading_level = int(tag[1])
            self.content_parts.append('\n\n' + '#' * self.heading_level + ' ')
        elif tag == 'img':
            src = attr_dict.get('data-src') or attr_dict.get('src')
            if src and not src.startswith('data:'):
                if 'wx_fmt=' in src and '#imgIndex=' not in src:
                    src += f'#imgIndex={self.current_img_index}'
                    self.current_img_index += 1
                self.content_parts.append(f'\n\n![Image]({src})\n\n')
        elif tag == 'pre':
            self.in_pre = True
            self.content_parts.append('\n\n```\n')
        elif tag == 'code':
            if not self.in_pre:
                self.in_code = True
                self.content_parts.append('`')
        elif tag == 'blockquote':
            self.in_blockquote = True
            self.content_parts.append('\n\n> ')
        elif tag == 'ul':
            self.list_stack.append(('ul', 0))
            self.content_parts.append('\n')
        elif tag == 'ol':
            self.list_stack.append(('ol', 0))
            self.content_parts.append('\n')
        elif tag == 'li':
            indent = '  ' * (len(self.list_stack) - 1)
            if self.list_stack and self.list_stack[-1][0] == 'ol':
                ltype, count = self.list_stack[-1]
                count += 1
                self.list_stack[-1] = (ltype, count)
                self.content_parts.append(f'\n{indent}{count}. ')
            else:
                self.content_parts.append(f'\n{indent}- ')
        elif tag in ('p', 'section', 'div'):
            if not self.heading_level and not self.in_pre:
                self.content_parts.append('\n\n')

        if is_bold and not self.heading_level:
            self.bold_stack += 1
            self.content_parts.append('**')

        if is_italic and not self.heading_level:
            self.italic_stack += 1
            self.content_parts.append('*')

        self.tag_stack.append((tag, attrs, is_bold, is_italic, False))

    def handle_endtag(self, tag):
        if not self.tag_stack:
            return

        last_tag, last_attrs, is_bold, is_italic, is_hidden = self.tag_stack.pop()

        if is_hidden:
            return

        if self.in_title and tag in ('h1', 'span', 'div'):
            self.in_title = False
        if self.in_author and tag in ('span', 'a'):
            self.in_author = False

        if not self.in_content:
            return

        if is_italic and not self.heading_level:
            if self.italic_stack > 0:
                self.italic_stack -= 1
                self.content_parts.append('*')

        if is_bold and not self.heading_level:
            if self.bold_stack > 0:
                self.bold_stack -= 1
                self.content_parts.append('**')

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.heading_level = 0
            self.content_parts.append('\n\n')
        elif tag == 'pre':
            self.in_pre = False
            self.content_parts.append('\n```\n\n')
        elif tag == 'code':
            if not self.in_pre and self.in_code:
                self.in_code = False
                self.content_parts.append('`')
        elif tag == 'blockquote':
            self.in_blockquote = False
            self.content_parts.append('\n\n')
        elif tag in ('ul', 'ol'):
            if self.list_stack:
                self.list_stack.pop()
            self.content_parts.append('\n')
        elif tag in ('p', 'section', 'div'):
            if not self.heading_level and not self.in_pre:
                self.content_parts.append('\n\n')

        if (tag == 'div' and dict(last_attrs).get('id') == 'js_content') or 'rich_media_content' in dict(last_attrs).get('class', ''):
            self.in_content = False

    def handle_data(self, data):
        if self.tag_stack and self.tag_stack[-1][4]:  # is_hidden
            return

        if self.in_title:
            self.title_parts.append(data)
        elif self.in_author:
            self.author_parts.append(data)
        elif self.in_content:
            self.content_parts.append(data)


def clean_markdown(raw_md):
    # Normalize consecutive empty lines
    lines = [line.rstrip() for line in raw_md.split('\n')]
    text = '\n'.join(lines)
    
    # Fix broken bold markers: e.g. **** or ** **
    text = re.sub(r'\*\*\s*\*\*', '', text)
    # Fix bold surrounding extra internal spaces: ** hello ** -> **hello**
    text = re.sub(r'\*\*\s+(.*?)\s+\*\*', r'**\1**', text)
    
    # Replace 3 or more newlines with 2 newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def fetch_wechat_article(url):
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')


def extract_metadata_and_date(html):
    # Try finding timestamp in scripts
    # var ct = "1788308400";
    ct_match = re.search(r'var\s+ct\s*=\s*[\'"]?(\d+)[\'"]?', html)
    pub_date = None
    if ct_match:
        try:
            ts = int(ct_match.group(1))
            pub_date = datetime.fromtimestamp(ts)
        except Exception:
            pass

    if not pub_date:
        # Check createDate
        cd_match = re.search(r'createDate\s*=\s*[\'"]([^\'"]+)[\'"]', html)
        if cd_match:
            try:
                pub_date = datetime.strptime(cd_match.group(1).strip(), '%Y-%m-%d')
            except Exception:
                pass

    if not pub_date:
        pub_date = datetime.now()

    date_prefix = pub_date.strftime('%y%m%d')
    return date_prefix


def sanitize_filename(name):
    # Remove slash, colon, backslash, etc.
    name = re.sub(r'[\\/:*?"<>|\r\n]+', '_', name)
    return name.strip()


def get_repo_root():
    cur = os.path.abspath(os.getcwd())
    while cur != os.path.dirname(cur):
        if os.path.exists(os.path.join(cur, '.git')):
            return cur
        cur = os.path.dirname(cur)
    # Fallback to 4 levels up from this script
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def parse_and_save(url, output_dir=None):
    if output_dir is None:
        output_dir = get_repo_root()

    print(f"Fetching: {url}")
    html = fetch_wechat_article(url)

    parser = WeChatArticleParser()
    parser.feed(html)

    title = unescape(''.join(parser.title_parts)).strip()
    if not title:
        # Fallback regex for title
        tm = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        if tm:
            title = unescape(tm.group(1)).strip()
        else:
            title = "未命名公众号文章"

    date_prefix = extract_metadata_and_date(html)
    raw_md = ''.join(parser.content_parts)
    clean_md = clean_markdown(raw_md)

    safe_title = sanitize_filename(title)
    filename = f"{date_prefix}-{safe_title}.md"
    file_path = os.path.join(output_dir, filename)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(clean_md)

    print(f"Saved successfully: {file_path}")
    print(f"Title: {title}")
    print(f"Date Prefix: {date_prefix}")
    return file_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 save_mp.py <wechat_url> [output_dir]")
        sys.exit(1)

    url = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else None
    parse_and_save(url, out_dir)
