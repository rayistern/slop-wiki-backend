#!/usr/bin/env python3
"""
Migration Script: Wiki.js to MediaWiki
Exports pages from Wiki.js and imports them to MediaWiki

Requirements:
    pip install mwclient httpx pypandoc

Usage:
    python migrate-to-mediawiki.py --wikijs-url http://localhost:3000 \
        --mediawiki-url https://slop.wiki \
        --bot-user "SlopBot@automation" \
        --bot-password "your-bot-password"
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

try:
    import mwclient
except ImportError:
    print("Error: mwclient not installed. Run: pip install mwclient")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WikiJSExporter:
    """Export pages from Wiki.js via GraphQL API."""
    
    def __init__(self, base_url: str, api_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.client = httpx.Client(timeout=30.0)
    
    def _graphql(self, query: str, variables: dict = None):
        """Execute a GraphQL query."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        response = self.client.post(
            f"{self.base_url}/graphql",
            headers=headers,
            json={"query": query, "variables": variables or {}}
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return result.get("data", {})
    
    def list_pages(self) -> list:
        """Get list of all pages."""
        query = """
        query {
            pages {
                list(orderBy: TITLE) {
                    id
                    path
                    title
                    description
                    createdAt
                    updatedAt
                }
            }
        }
        """
        data = self._graphql(query)
        return data.get("pages", {}).get("list", [])
    
    def get_page_content(self, page_id: int) -> dict:
        """Get full page content by ID."""
        query = """
        query ($id: Int!) {
            pages {
                single(id: $id) {
                    id
                    path
                    title
                    description
                    content
                    contentType
                    createdAt
                    updatedAt
                    tags {
                        tag
                    }
                }
            }
        }
        """
        data = self._graphql(query, {"id": page_id})
        return data.get("pages", {}).get("single", {})
    
    def export_all(self, output_dir: str = "wikijs_export") -> list:
        """Export all pages to JSON files."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        pages = self.list_pages()
        logger.info(f"Found {len(pages)} pages to export")
        
        exported = []
        for page_meta in pages:
            try:
                page = self.get_page_content(page_meta['id'])
                if not page:
                    logger.warning(f"Could not fetch page {page_meta['id']}")
                    continue
                
                # Save to JSON
                filename = f"{page['id']}_{page['path'].replace('/', '_')}.json"
                filepath = output_path / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(page, f, indent=2, ensure_ascii=False)
                
                exported.append(page)
                logger.info(f"Exported: {page['title']} ({page['path']})")
                
            except Exception as e:
                logger.error(f"Error exporting page {page_meta.get('id')}: {e}")
        
        logger.info(f"Exported {len(exported)} pages to {output_dir}/")
        return exported


class MarkdownToWikitext:
    """Convert Markdown to MediaWiki wikitext."""
    
    @staticmethod
    def convert_with_pandoc(markdown: str) -> str:
        """Use pandoc for conversion (best quality)."""
        try:
            result = subprocess.run(
                ['pandoc', '-f', 'markdown', '-t', 'mediawiki'],
                input=markdown,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except FileNotFoundError:
            logger.warning("pandoc not found, falling back to manual conversion")
            return MarkdownToWikitext.convert_manual(markdown)
        except subprocess.CalledProcessError as e:
            logger.error(f"pandoc error: {e.stderr}")
            return MarkdownToWikitext.convert_manual(markdown)
    
    @staticmethod
    def convert_manual(markdown: str) -> str:
        """Manual conversion for basic Markdown (fallback)."""
        text = markdown
        
        # Headers: # -> =
        text = re.sub(r'^###### (.+)$', r'====== \1 ======', text, flags=re.MULTILINE)
        text = re.sub(r'^##### (.+)$', r'===== \1 =====', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'==== \1 ====', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'=== \1 ===', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'== \1 ==', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'= \1 =', text, flags=re.MULTILINE)
        
        # Bold: **text** -> '''text'''
        text = re.sub(r'\*\*(.+?)\*\*', r"'''\1'''", text)
        
        # Italic: *text* -> ''text''
        text = re.sub(r'\*(.+?)\*', r"''\1''", text)
        
        # Links: [text](url) -> [url text]
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[\2 \1]', text)
        
        # Internal links: [[Page]] stays the same
        
        # Code blocks: ```lang -> <syntaxhighlight lang="lang">
        text = re.sub(
            r'```(\w+)?\n(.*?)\n```',
            lambda m: f'<syntaxhighlight lang="{m.group(1) or "text"}">\n{m.group(2)}\n</syntaxhighlight>',
            text,
            flags=re.DOTALL
        )
        
        # Inline code: `code` -> <code>code</code>
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # Unordered lists: - item -> * item
        text = re.sub(r'^- ', '* ', text, flags=re.MULTILINE)
        
        # Ordered lists: 1. item -> # item
        text = re.sub(r'^\d+\. ', '# ', text, flags=re.MULTILINE)
        
        # Horizontal rules
        text = re.sub(r'^---+$', '----', text, flags=re.MULTILINE)
        
        # Images: ![alt](url) -> [[File:url|alt]]
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'[[File:\2|\1]]', text)
        
        return text


class MediaWikiImporter:
    """Import pages to MediaWiki."""
    
    def __init__(self, site_url: str, bot_user: str, bot_password: str):
        # Parse URL to get host and path
        if site_url.startswith('http://'):
            scheme = 'http'
            host = site_url[7:]
        elif site_url.startswith('https://'):
            scheme = 'https'
            host = site_url[8:]
        else:
            scheme = 'https'
            host = site_url
        
        host = host.rstrip('/')
        
        self.site = mwclient.Site(host, path='/', scheme=scheme)
        self.site.login(bot_user, bot_password)
        logger.info(f"Logged in to MediaWiki as {bot_user}")
    
    def create_page(self, title: str, content: str, summary: str = "Migration from Wiki.js") -> bool:
        """Create or update a page."""
        try:
            page = self.site.pages[title]
            page.save(content, summary=summary)
            logger.info(f"Created/updated page: {title}")
            return True
        except Exception as e:
            logger.error(f"Error creating page {title}: {e}")
            return False
    
    def import_from_export(self, export_dir: str, namespace_prefix: str = "") -> dict:
        """Import all exported pages."""
        export_path = Path(export_dir)
        if not export_path.exists():
            raise FileNotFoundError(f"Export directory not found: {export_dir}")
        
        results = {"success": 0, "failed": 0, "pages": []}
        
        for json_file in export_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                
                # Convert title to MediaWiki format
                title = page_data.get('title', page_data.get('path', 'Untitled'))
                if namespace_prefix:
                    title = f"{namespace_prefix}:{title}"
                
                # Clean up title
                title = title.replace('/', ':')  # Subpages
                
                # Get content and convert
                content = page_data.get('content', '')
                content_type = page_data.get('contentType', 'markdown')
                
                if content_type == 'markdown':
                    wikitext = MarkdownToWikitext.convert_with_pandoc(content)
                else:
                    wikitext = content
                
                # Add metadata as footer
                tags = page_data.get('tags', [])
                tag_names = [t.get('tag', t) if isinstance(t, dict) else t for t in tags]
                
                if tag_names:
                    wikitext += "\n\n"
                    for tag in tag_names:
                        wikitext += f"[[Category:{tag}]]\n"
                
                # Add migration notice
                wikitext = f"<!-- Migrated from Wiki.js on {datetime.now().isoformat()} -->\n" + wikitext
                
                # Import
                summary = f"Migration from Wiki.js (original path: {page_data.get('path', 'unknown')})"
                if self.create_page(title, wikitext, summary):
                    results["success"] += 1
                    results["pages"].append({"title": title, "status": "success"})
                else:
                    results["failed"] += 1
                    results["pages"].append({"title": title, "status": "failed"})
                    
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                results["failed"] += 1
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Migrate Wiki.js to MediaWiki")
    
    parser.add_argument('--wikijs-url', required=True, help='Wiki.js base URL')
    parser.add_argument('--wikijs-token', help='Wiki.js API token (optional)')
    parser.add_argument('--mediawiki-url', required=True, help='MediaWiki base URL')
    parser.add_argument('--bot-user', required=True, help='MediaWiki bot username (e.g., BotName@password-name)')
    parser.add_argument('--bot-password', required=True, help='MediaWiki bot password')
    parser.add_argument('--export-dir', default='wikijs_export', help='Directory for exported pages')
    parser.add_argument('--namespace', default='', help='MediaWiki namespace prefix for imported pages')
    parser.add_argument('--export-only', action='store_true', help='Only export from Wiki.js, do not import')
    parser.add_argument('--import-only', action='store_true', help='Only import to MediaWiki from existing export')
    
    args = parser.parse_args()
    
    # Export from Wiki.js
    if not args.import_only:
        logger.info("=== Exporting from Wiki.js ===")
        exporter = WikiJSExporter(args.wikijs_url, args.wikijs_token)
        try:
            pages = exporter.export_all(args.export_dir)
            logger.info(f"Export complete: {len(pages)} pages")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            if not args.export_only:
                sys.exit(1)
    
    if args.export_only:
        logger.info("Export-only mode, skipping import")
        return
    
    # Import to MediaWiki
    logger.info("=== Importing to MediaWiki ===")
    try:
        importer = MediaWikiImporter(args.mediawiki_url, args.bot_user, args.bot_password)
        results = importer.import_from_export(args.export_dir, args.namespace)
        
        logger.info(f"Import complete: {results['success']} succeeded, {results['failed']} failed")
        
        # Save results
        results_file = Path(args.export_dir) / 'migration_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
