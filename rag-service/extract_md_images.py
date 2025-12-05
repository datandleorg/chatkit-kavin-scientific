#!/usr/bin/env python3
"""
Markdown Image Extractor and Base64 Converter

This script extracts all images from markdown files (base64, URLs, local paths)
and converts them to base64 format with detailed logging.

Usage:
    python extract_md_images.py input.md [--output-dir output_directory] [--download-urls]
    python extract_md_images.py input.md --verbose
    python extract_md_images.py input.md --save-images
"""

import argparse
import os
import sys
import re
import base64
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import mimetypes

try:
    from markdown_it import MarkdownIt
    HAS_MARKDOWN_IT = True
except ImportError:
    HAS_MARKDOWN_IT = False
    try:
        import mistune
        HAS_MISTUNE = True
    except ImportError:
        HAS_MISTUNE = False
        print("Warning: markdown parser not installed. Using regex-only mode.")
        print("Install with: pip install markdown-it-py OR pip install mistune")

try:
    from PIL import Image
    from io import BytesIO
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL/Pillow not installed. Image processing will be limited.")
    print("Install with: pip install pillow")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests not installed. URL image downloads will be disabled.")
    print("Install with: pip install requests")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MarkdownImageExtractor:
    """Extract images from markdown files and convert to base64"""
    
    def __init__(self, file_path: Path, output_dir: Optional[Path] = None, download_urls: bool = False, save_images: bool = False):
        self.file_path = Path(file_path)
        self.output_dir = output_dir
        self.download_urls = download_urls
        self.save_images = save_images
        self.markdown_dir = self.file_path.parent
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")
        
        # Create output directory if specified
        if self.output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized extractor for: {self.file_path}")
        logger.info(f"Markdown directory: {self.markdown_dir}")
        if self.output_dir:
            logger.info(f"Output directory: {self.output_dir}")
    
    def extract_all_images(self) -> Dict[str, Any]:
        """
        Extract all images from markdown file using Markdown parser + regex hybrid approach
        
        Returns:
            Dictionary containing all extracted image information
        """
        logger.info("=" * 80)
        logger.info(f"Starting image extraction from: {self.file_path.name}")
        logger.info("=" * 80)
        
        # Read markdown content
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"File size: {len(content)} characters")
        logger.info(f"Lines: {len(content.splitlines())}")
        logger.info("-" * 80)
        
        # Extract all image references using parser + regex hybrid
        all_images = []
        
        # Method 2: Use Markdown parser for robust extraction
        if HAS_MARKDOWN_IT:
            logger.info("Using markdown-it-py parser for extraction...")
            base64_images = self._extract_base64_images_with_parser(content)
        elif HAS_MISTUNE:
            logger.info("Using mistune parser for extraction...")
            base64_images = self._extract_base64_images_with_mistune(content)
        else:
            logger.info("Using regex-only method for extraction...")
            base64_images = self._extract_base64_images_regex(content)
        
        all_images.extend(base64_images)
        logger.info(f"Found {len(base64_images)} base64 embedded images (from markdown)")
        
        # Pattern 1b: HTML img tags with base64 data URIs
        logger.info("Searching for HTML <img> tags with base64 data...")
        html_img_images = self._extract_html_img_tags(content)
        
        # Deduplicate: check if HTML images were already found by markdown parser
        found_base64_keys = {img["base64_data"][:50] for img in all_images if "base64_data" in img}
        for html_img in html_img_images:
            img_key = html_img["base64_data"][:50]
            if img_key not in found_base64_keys:
                all_images.append(html_img)
                found_base64_keys.add(img_key)
            else:
                logger.debug(f"  Skipping duplicate HTML img tag (already found by markdown parser)")
        
        logger.info(f"Found {len(html_img_images)} HTML img tags ({len([img for img in all_images if img.get('extraction_method') == 'html_img_tag'])}) unique)")
        
        # Pattern 2: Standard markdown images with URLs
        # Format: ![alt](url) or ![alt](http://example.com/image.png)
        logger.info("Searching for URL-based images...")
        url_images = self._extract_url_images(content)
        all_images.extend(url_images)
        logger.info(f"Found {len(url_images)} URL-based images")
        
        # Pattern 3: Local file paths
        # Format: ![alt](./path/to/image.png) or ![alt](images/pic.jpg)
        logger.info("Searching for local file path images...")
        local_images = self._extract_local_images(content)
        all_images.extend(local_images)
        logger.info(f"Found {len(local_images)} local file path images")
        
        logger.info("-" * 80)
        logger.info(f"Total images found: {len(all_images)}")
        logger.info("=" * 80)
        
        # Process and convert images
        processed_images = []
        for idx, img_info in enumerate(all_images, 1):
            logger.info("")
            logger.info(f"Processing Image #{idx}/{len(all_images)}")
            logger.info(f"  Type: {img_info['type']}")
            logger.info(f"  Alt text: '{img_info.get('alt_text', 'N/A')}'")
            logger.info(f"  Original source: {img_info['source']}")
            
            try:
                processed = self._process_image(img_info, idx)
                processed_images.append(processed)
                
                logger.info(f"  ✓ Successfully processed")
                logger.info(f"  Format: {processed.get('format', 'unknown')}")
                logger.info(f"  Size: {processed.get('size_bytes', 0):,} bytes ({processed.get('size_bytes', 0) / 1024:.2f} KB)")
                logger.info(f"  Dimensions: {processed.get('width', 'N/A')}x{processed.get('height', 'N/A')}")
                logger.info(f"  Base64 length: {len(processed.get('base64_data', '')):,} characters")
                
            except Exception as e:
                logger.error(f"  ✗ Failed to process image: {e}")
                processed_images.append({
                    **img_info,
                    "status": "error",
                    "error": str(e)
                })
        
        # Generate summary
        summary = {
            "file_path": str(self.file_path),
            "total_images_found": len(all_images),
            "successfully_processed": len([img for img in processed_images if img.get('status') != 'error']),
            "failed": len([img for img in processed_images if img.get('status') == 'error']),
            "images": processed_images,
            "statistics": {
                "base64_embedded": len([img for img in processed_images if img.get('type') == 'base64']),
                "url_downloaded": len([img for img in processed_images if img.get('type') == 'url']),
                "local_files": len([img for img in processed_images if img.get('type') == 'local']),
            }
        }
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("EXTRACTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total images found: {summary['total_images_found']}")
        logger.info(f"Successfully processed: {summary['successfully_processed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"  - Base64 embedded: {summary['statistics']['base64_embedded']}")
        logger.info(f"  - URL downloaded: {summary['statistics']['url_downloaded']}")
        logger.info(f"  - Local files: {summary['statistics']['local_files']}")
        logger.info("=" * 80)
        
        # Save results if output directory specified
        if self.output_dir:
            self._save_results(summary)
        
        return summary
    
    def _extract_base64_images_regex(self, content: str) -> List[Dict[str, Any]]:
        """Extract base64 embedded images using regex only"""
        # Improved regex pattern: handles optional alt text, multiple formats
        pattern = r'!\[(.*?)\]\(data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+)\)'
        images = []
        
        for match in re.finditer(pattern, content):
            alt_text = match.group(1).strip()
            image_format = match.group(2).lower()
            base64_data = match.group(3)
            
            images.append({
                "type": "base64",
                "alt_text": alt_text,
                "format": image_format,
                "source": f"data:image/{image_format};base64,...",
                "base64_data": base64_data,
                "position_in_text": match.start(),
                "raw_match": match.group(0),
                "extraction_method": "regex"
            })
        
        return images
    
    def _extract_base64_images_with_parser(self, content: str) -> List[Dict[str, Any]]:
        """Extract base64 embedded images using markdown-it-py parser (Method 2) - More robust"""
        images = []
        
        # Parse markdown using markdown-it-py
        md = MarkdownIt()
        tokens = md.parse(content)
        
        # Regex pattern for base64 data URIs within token content
        pattern = re.compile(r'data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+)')
        
        logger.debug(f"Parsed {len(tokens)} tokens from markdown")
        
        for token in tokens:
            # Check inline tokens for image content
            if token.type == "inline" and token.content:
                logger.debug(f"Processing inline token: {token.content[:100]}...")
                
                # Search for base64 images in the inline content
                for match in pattern.finditer(token.content):
                    image_format = match.group(1).lower()
                    base64_data = match.group(2)
                    
                    # Try to find alt text from surrounding context
                    # Look for markdown image syntax pattern around this match
                    match_start = match.start()
                    match_end = match.end()
                    
                    # Try to extract alt text by looking backwards for ![ and forwards for ]
                    context_start = max(0, match_start - 200)
                    context_end = min(len(token.content), match_end + 50)
                    context = token.content[context_start:context_end]
                    
                    # Look for ![alt]( pattern before the data URI
                    alt_pattern = re.compile(r'!\[([^\]]*)\]\(data:image/')
                    alt_match = alt_pattern.search(context)
                    alt_text = alt_match.group(1).strip() if alt_match else ""
                    
                    # Find position in original content
                    # Token map gives us line range
                    line_start = token.map[0] if token.map else 0
                    full_lines = content.split('\n')[:line_start]
                    char_offset = sum(len(line) + 1 for line in full_lines)  # +1 for newline
                    position = char_offset + match_start
                    
                    # Create unique key to avoid duplicates
                    img_key = base64_data[:50]
                    
                    # Check if we already have this image
                    if not any(existing.get("base64_data", "")[:50] == img_key for existing in images):
                        images.append({
                            "type": "base64",
                            "alt_text": alt_text,
                            "format": image_format,
                            "source": f"data:image/{image_format};base64,...",
                            "base64_data": base64_data,
                            "position_in_text": position,
                            "raw_match": match.group(0),
                            "extraction_method": "markdown-it-py",
                            "token_type": token.type,
                            "line_number": line_start + 1
                        })
                        logger.debug(f"Found base64 image: format={image_format}, alt='{alt_text}', size={len(base64_data)} chars")
            
            # Also check image tokens directly
            elif token.type == "image":
                logger.debug(f"Found image token: {token.attrs if hasattr(token, 'attrs') else 'no attrs'}")
                if hasattr(token, 'attrs') and 'src' in token.attrs:
                    src = token.attrs['src']
                    if src.startswith('data:image/'):
                        # Extract from data URI
                        match = pattern.search(src)
                        if match:
                            image_format = match.group(1).lower()
                            base64_data = match.group(2)
                            alt_text = token.attrs.get('alt', '') if hasattr(token, 'attrs') else ""
                            
                            # Find position
                            line_start = token.map[0] if token.map else 0
                            full_lines = content.split('\n')[:line_start]
                            char_offset = sum(len(line) + 1 for line in full_lines)
                            position = char_offset
                            
                            img_key = base64_data[:50]
                            if not any(existing.get("base64_data", "")[:50] == img_key for existing in images):
                                images.append({
                                    "type": "base64",
                                    "alt_text": alt_text,
                                    "format": image_format,
                                    "source": f"data:image/{image_format};base64,...",
                                    "base64_data": base64_data,
                                    "position_in_text": position,
                                    "raw_match": src[:100] + "...",
                                    "extraction_method": "markdown-it-py",
                                    "token_type": "image",
                                    "line_number": line_start + 1
                                })
                                logger.debug(f"Found image token with base64: format={image_format}")
        
        # Fallback: also do a regex pass on full content to catch anything missed
        logger.debug("Running regex fallback pass...")
        regex_images = self._extract_base64_images_regex(content)
        for regex_img in regex_images:
            img_key = regex_img["base64_data"][:50]
            if not any(existing.get("base64_data", "")[:50] == img_key for existing in images):
                logger.debug(f"Regex fallback found additional image")
                images.append({**regex_img, "extraction_method": "regex_fallback"})
        
        logger.info(f"Parser found {len(images)} unique base64 images")
        return images
    
    def _extract_base64_images_with_mistune(self, content: str) -> List[Dict[str, Any]]:
        """Extract base64 embedded images using mistune parser"""
        images = []
        
        # Parse markdown
        renderer = mistune.create_markdown(renderer=mistune.HTMLRenderer())
        html = renderer(content)
        
        # Extract from HTML output using regex
        pattern = re.compile(r'<img[^>]*src=["\']data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+)["\']')
        alt_pattern = re.compile(r'alt=["\']([^"\']*)["\']')
        
        for match in pattern.finditer(html):
            image_format = match.group(1).lower()
            base64_data = match.group(2)
            
            # Try to extract alt text
            alt_match = alt_pattern.search(match.group(0))
            alt_text = alt_match.group(1) if alt_match else ""
            
            # Find in original content
            data_uri = f"data:image/{image_format};base64,{base64_data}"
            position = content.find(data_uri)
            
            images.append({
                "type": "base64",
                "alt_text": alt_text,
                "format": image_format,
                "source": f"data:image/{image_format};base64,...",
                "base64_data": base64_data,
                "position_in_text": position if position >= 0 else 0,
                "extraction_method": "mistune",
                "raw_match": data_uri
            })
        
        # Also do regex pass as fallback
        regex_images = self._extract_base64_images_regex(content)
        for regex_img in regex_images:
            if not any(existing["base64_data"][:50] == regex_img["base64_data"][:50] 
                      for existing in images):
                images.append({**regex_img, "extraction_method": "regex_fallback"})
        
        return images
    
    def _extract_html_img_tags(self, content: str) -> List[Dict[str, Any]]:
        """Extract base64 images from HTML <img> tags"""
        images = []
        
        # Pattern for HTML img tags with base64 data URIs
        # Matches: <img src="data:image/png;base64,..." alt="..." />
        # Or: <img src="data:image/png;base64,..." alt="..." style="..."/>
        pattern = re.compile(
            r'<img[^>]*src=["\'](data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+))["\'][^>]*>',
            re.IGNORECASE
        )
        alt_pattern = re.compile(r'alt=["\']([^"\']*)["\']', re.IGNORECASE)
        
        found_keys = set()
        
        for match in pattern.finditer(content):
            # Extract the full data URI
            full_data_uri = match.group(1)
            image_format = match.group(2).lower()
            base64_data = match.group(3)
            
            # Use first 50 chars as unique key
            img_key = base64_data[:50]
            
            # Skip if already found
            if img_key in found_keys:
                continue
            found_keys.add(img_key)
            
            # Try to extract alt text from the img tag
            img_tag_content = match.group(0)
            alt_match = alt_pattern.search(img_tag_content)
            alt_text = alt_match.group(1) if alt_match else ""
            
            # Find position in original content
            position = match.start()
            
            images.append({
                "type": "base64",
                "alt_text": alt_text,
                "format": image_format,
                "source": f"data:image/{image_format};base64,...",
                "base64_data": base64_data,
                "position_in_text": position,
                "raw_match": img_tag_content[:200] + "..." if len(img_tag_content) > 200 else img_tag_content,
                "extraction_method": "html_img_tag"
            })
            logger.info(f"  ✓ Found HTML img tag: format={image_format}, alt='{alt_text}', size={len(base64_data)} chars")
        
        return images
    
    def _extract_base64_images(self, content: str) -> List[Dict[str, Any]]:
        """Legacy method - redirects to appropriate extraction method"""
        if HAS_MARKDOWN_IT:
            return self._extract_base64_images_with_parser(content)
        elif HAS_MISTUNE:
            return self._extract_base64_images_with_mistune(content)
        else:
            return self._extract_base64_images_regex(content)
    
    def _extract_url_images(self, content: str) -> List[Dict[str, Any]]:
        """Extract URL-based images"""
        # Pattern: ![alt](http://... or https://... or ![alt](http://...)
        pattern = r'!\[([^\]]*)\]\((https?://[^\)]+)\)'
        images = []
        
        for match in re.finditer(pattern, content):
            alt_text = match.group(1)
            url = match.group(2)
            
            images.append({
                "type": "url",
                "alt_text": alt_text,
                "source": url,
                "url": url,
                "position_in_text": match.start(),
                "raw_match": match.group(0)
            })
        
        return images
    
    def _extract_local_images(self, content: str) -> List[Dict[str, Any]]:
        """Extract local file path images"""
        # Pattern: ![alt](./path) or ![alt](path/to/image.png) or ![alt](../images/pic.jpg)
        # Exclude URLs and base64
        pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        images = []
        
        for match in re.finditer(pattern, content):
            alt_text = match.group(1)
            path = match.group(2).strip()
            
            # Skip if it's a URL or base64
            if path.startswith(('http://', 'https://', 'data:')):
                continue
            
            # Check if it's a local file path
            images.append({
                "type": "local",
                "alt_text": alt_text,
                "source": path,
                "local_path": path,
                "position_in_text": match.start(),
                "raw_match": match.group(0)
            })
        
        return images
    
    def _process_image(self, img_info: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Process an image and convert to base64"""
        img_type = img_info['type']
        
        if img_type == 'base64':
            return self._process_base64_image(img_info, index)
        elif img_type == 'url':
            return self._process_url_image(img_info, index)
        elif img_type == 'local':
            return self._process_local_image(img_info, index)
        else:
            raise ValueError(f"Unknown image type: {img_type}")
    
    def _process_base64_image(self, img_info: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Process base64 embedded image"""
        if not HAS_PIL:
            # Return basic info without PIL
            base64_data = img_info['base64_data']
            try:
                image_bytes = base64.b64decode(base64_data)
                return {
                    **img_info,
                    "status": "success",
                    "size_bytes": len(image_bytes),
                    "format": img_info.get('format', 'unknown'),
                    "mime_type": f"image/{img_info.get('format', 'unknown')}",
                    "note": "PIL not available, limited image info"
                }
            except Exception as e:
                raise Exception(f"Failed to decode base64 image: {e}")
        
        base64_data = img_info['base64_data']
        
        # Decode to get image bytes
        try:
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_bytes))
            
            # Get image info
            width, height = image.size
            format_name = image.format or img_info.get('format', 'unknown')
            
            result = {
                **img_info,
                "status": "success",
                "base64_data": base64_data,  # Keep original
                "size_bytes": len(image_bytes),
                "width": width,
                "height": height,
                "format": format_name.lower(),
                "mime_type": f"image/{format_name.lower()}"
            }
            
            # Save image if requested
            if self.save_images and self.output_dir:
                filename = f"image_{index}_{img_info.get('alt_text', 'unnamed').replace(' ', '_')[:20]}.{format_name.lower()}"
                filepath = self.output_dir / filename
                image.save(filepath)
                result["saved_path"] = str(filepath)
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to decode base64 image: {e}")
    
    def _process_url_image(self, img_info: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Process URL-based image"""
        url = img_info['url']
        
        if not self.download_urls:
            return {
                **img_info,
                "status": "skipped",
                "message": "URL download disabled (use --download-urls to enable)"
            }
        
        if not HAS_REQUESTS:
            return {
                **img_info,
                "status": "skipped",
                "message": "requests library not available (install with: pip install requests)"
            }
        
        logger.info(f"  Downloading from URL: {url}")
        
        try:
            response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            
            image_bytes = response.content
            
            # Convert to base64
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            
            if HAS_PIL:
                image = Image.open(BytesIO(image_bytes))
                width, height = image.size
                format_name = image.format or 'unknown'
            else:
                # Try to guess format from URL or headers
                width, height = None, None
                format_name = 'unknown'
            
            # Detect format from URL or content
            mime_type = response.headers.get('Content-Type', f'image/{format_name.lower()}')
            
            result = {
                **img_info,
                "status": "success",
                "base64_data": base64_data,
                "size_bytes": len(image_bytes),
                "width": width,
                "height": height,
                "format": format_name.lower() if format_name != 'unknown' else 'unknown',
                "mime_type": mime_type,
                "download_status_code": response.status_code
            }
            
            # Save image if requested
            if self.save_images and self.output_dir and HAS_PIL:
                filename = f"image_{index}_url_{url.split('/')[-1][:20]}.{format_name.lower()}"
                filepath = self.output_dir / filename
                image.save(filepath)
                result["saved_path"] = str(filepath)
            elif self.save_images and self.output_dir:
                # Save raw bytes without PIL
                filename = f"image_{index}_url_{url.split('/')[-1][:20]}.bin"
                filepath = self.output_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                result["saved_path"] = str(filepath)
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to download from URL: {e}")
    
    def _process_local_image(self, img_info: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Process local file path image"""
        local_path = img_info['local_path']
        
        # Resolve relative path
        if local_path.startswith('./') or not local_path.startswith('/'):
            # Relative to markdown file directory
            resolved_path = (self.markdown_dir / local_path).resolve()
        else:
            resolved_path = Path(local_path)
        
        logger.info(f"  Resolved path: {resolved_path}")
        
        if not resolved_path.exists():
            raise FileNotFoundError(f"Image file not found: {resolved_path}")
        
        try:
            # Read image file
            with open(resolved_path, 'rb') as f:
                image_bytes = f.read()
            
            if HAS_PIL:
                image = Image.open(BytesIO(image_bytes))
                width, height = image.size
                format_name = image.format or resolved_path.suffix[1:].lower()
            else:
                width, height = None, None
                format_name = resolved_path.suffix[1:].lower() if resolved_path.suffix else 'unknown'
            
            # Convert to base64
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(str(resolved_path))
            if not mime_type:
                mime_type = f"image/{format_name.lower()}"
            
            result = {
                **img_info,
                "status": "success",
                "base64_data": base64_data,
                "resolved_path": str(resolved_path),
                "size_bytes": len(image_bytes),
                "width": width,
                "height": height,
                "format": format_name.lower(),
                "mime_type": mime_type
            }
            
            # Save copy if requested
            if self.save_images and self.output_dir and HAS_PIL:
                filename = f"image_{index}_{resolved_path.stem}.{format_name.lower()}"
                filepath = self.output_dir / filename
                image.save(filepath)
                result["saved_path"] = str(filepath)
            elif self.save_images and self.output_dir:
                # Save raw bytes without PIL
                filename = f"image_{index}_{resolved_path.stem}.bin"
                filepath = self.output_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                result["saved_path"] = str(filepath)
            
            return result
            
        except Exception as e:
            raise Exception(f"Failed to read local image file: {e}")
    
    def _save_results(self, summary: Dict[str, Any]):
        """Save extraction results to JSON file"""
        if not self.output_dir:
            return
        
        output_file = self.output_dir / f"{self.file_path.stem}_images.json"
        
        # Create a copy without full base64 data for JSON (can be large)
        summary_copy = summary.copy()
        for img in summary_copy.get('images', []):
            if 'base64_data' in img and len(img['base64_data']) > 100:
                img['base64_data_preview'] = img['base64_data'][:100] + "... (truncated)"
                img['base64_data_length'] = len(img['base64_data'])
                del img['base64_data']  # Remove full base64 to keep file size manageable
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary_copy, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_file}")
        
        # Also save base64 data separately if needed
        base64_file = self.output_dir / f"{self.file_path.stem}_base64_images.json"
        with open(base64_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Full base64 data saved to: {base64_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract images from markdown files and convert to base64',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all images from a markdown file
  python extract_md_images.py document.md

  # Extract and save images to output directory
  python extract_md_images.py document.md --output-dir ./output --save-images

  # Download images from URLs
  python extract_md_images.py document.md --download-urls

  # Verbose logging
  python extract_md_images.py document.md --verbose
        """
    )
    
    parser.add_argument('file', type=str, help='Path to markdown file')
    parser.add_argument('--output-dir', '-o', type=str, help='Output directory for results')
    parser.add_argument('--download-urls', action='store_true', help='Download images from URLs')
    parser.add_argument('--save-images', '-s', action='store_true', help='Save extracted images as files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    try:
        extractor = MarkdownImageExtractor(
            file_path=Path(args.file),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            download_urls=args.download_urls,
            save_images=args.save_images
        )
        
        summary = extractor.extract_all_images()
        
        # Print summary
        print("\n" + "=" * 80)
        print("EXTRACTION COMPLETE")
        print("=" * 80)
        print(f"File: {summary['file_path']}")
        print(f"Total images found: {summary['total_images_found']}")
        print(f"Successfully processed: {summary['successfully_processed']}")
        print(f"Failed: {summary['failed']}")
        
        if args.output_dir:
            print(f"\nResults saved to: {args.output_dir}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=args.verbose)
        return 1


if __name__ == '__main__':
    sys.exit(main())

