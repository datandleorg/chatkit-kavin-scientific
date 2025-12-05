#!/usr/bin/env python3
"""
PDF Text, Table, and Image Extractor using Docling

This script extracts text, tables, and images from PDF files using Docling library.
Docling provides advanced PDF processing capabilities with better table detection
and structured content extraction compared to traditional libraries.

Requirements:
    pip install docling-parse pillow

Usage:
    python pdf_extractor_docling.py input.pdf [--output-dir output_directory] [--extract-all]
    python pdf_extractor_docling.py input.pdf --extract-text
    python pdf_extractor_docling.py input.pdf --extract-tables
    python pdf_extractor_docling.py input.pdf --extract-images
"""

import argparse
import os
import sys
import json
import base64
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    from docling_parse.pdf_parser import pdf_parser_v2
    from PIL import Image
except ImportError as e:
    print(f"Error: Required packages not installed. Please install them using:")
    print("pip install docling-parse pillow")
    print(f"Missing package: {e}")
    sys.exit(1)


class DoclingPDFExtractor:
    """PDF extraction class using Docling"""
    
    def __init__(self, pdf_path: str):
        """
        Initialize PDF extractor
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.output_dir = None
        self.parsed_data = None
        
    def set_output_directory(self, output_dir: str):
        """Set output directory for extracted content"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def parse_pdf(self) -> Dict[str, Any]:
        """
        Parse PDF using Docling
        
        Returns:
            Dictionary containing parsed document data
        """
        if self.parsed_data is None:
            print(f"Parsing PDF: {self.pdf_path}")
            # Use pdf_parser_v2 to parse the PDF
            parser = pdf_parser_v2(str(self.pdf_path))
            parser.load_document('doc1', str(self.pdf_path))
            self.parsed_data = parser.parse_pdf_from_key('doc1')
            print(f"Parsed {len(self.parsed_data['pages'])} pages")
        
        return self.parsed_data
    
    def extract_text(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract text from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted text data
        """
        parsed_data = self.parse_pdf()
        
        text_data = {
            "total_pages": len(parsed_data['pages']),
            "text_elements": [],
            "full_text": "",
            "pages": {}
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(parsed_data['pages']))
        
        for page_idx in pages_to_process:
            if 0 <= page_idx < len(parsed_data['pages']):
                page = parsed_data['pages'][page_idx]
                sanitized_page = page['sanitized']
                
                page_text = ""
                page_elements = []
                
                # Extract text from cells
                if 'cells' in sanitized_page and 'data' in sanitized_page['cells']:
                    for cell_idx, cell_data in enumerate(sanitized_page['cells']['data']):
                        # Cell data is a list where text is at index 12
                        if len(cell_data) > 12 and cell_data[12]:
                            text_content = str(cell_data[12])
                            if text_content.strip():
                                element = {
                                    "element_index": cell_idx,
                                    "text": text_content,
                                    "char_count": len(text_content),
                                    "word_count": len(text_content.split()),
                                    "page": page_idx,
                                    "element_type": "cell",
                                    "bbox": [cell_data[0], cell_data[1], cell_data[2], cell_data[3]] if len(cell_data) > 3 else None
                                }
                                page_elements.append(element)
                                page_text += f"\n{text_content}"
                
                # Extract text from lines (lines appear to be geometric shapes, not text)
                # Lines in this structure seem to be drawing elements, not text lines
                # We'll skip lines for now since they don't contain text
                
                text_data["text_elements"].extend(page_elements)
                text_data["full_text"] += page_text
                
                text_data["pages"][str(page_idx)] = {
                    "text": page_text,
                    "char_count": len(page_text),
                    "word_count": len(page_text.split()),
                    "elements": page_elements
                }
        
        return text_data
    
    def extract_tables(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract tables from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted table data
        """
        parsed_data = self.parse_pdf()
        
        tables_data = {
            "total_pages": len(parsed_data['pages']),
            "table_elements": [],
            "pages": {},
            "total_tables": 0
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(parsed_data['pages']))
        
        for page_idx in pages_to_process:
            if 0 <= page_idx < len(parsed_data['pages']):
                page = parsed_data['pages'][page_idx]
                sanitized_page = page['sanitized']
                
                page_tables = []
                
                # Extract tables from cells (group cells by table structure)
                if 'cells' in sanitized_page and 'data' in sanitized_page['cells']:
                    # Group cells that might form tables based on their positions
                    cells_data = sanitized_page['cells']['data']
                    if cells_data:
                        # Simple table detection: group cells by similar y-coordinates
                        table_groups = {}
                        for cell_data in cells_data:
                            if len(cell_data) > 12 and cell_data[12]:  # Check if text exists
                                y_pos = cell_data[1]  # y-coordinate (y0)
                                # Group cells within 10 pixels of each other vertically
                                group_key = round(y_pos / 10) * 10
                                if group_key not in table_groups:
                                    table_groups[group_key] = []
                                table_groups[group_key].append(cell_data)
                        
                        # Convert groups to table structures
                        for table_idx, (y_pos, cell_group) in enumerate(table_groups.items()):
                            if len(cell_group) > 1:  # Only consider groups with multiple cells
                                # Sort cells by x-coordinate
                                cell_group.sort(key=lambda c: c[0])  # Sort by x0
                                
                                table_data = []
                                for cell_data in cell_group:
                                    table_data.append(str(cell_data[12]) if len(cell_data) > 12 else '')
                                
                                table_element = {
                                    "element_index": table_idx,
                                    "page": page_idx,
                                    "bbox": None,  # Could calculate from cell bboxes
                                    "rows": 1,
                                    "cols": len(table_data),
                                    "data": [table_data],  # Single row for now
                                    "metadata": {
                                        "table_type": "detected_from_cells",
                                        "y_position": y_pos
                                    }
                                }
                                
                                page_tables.append(table_element)
                
                tables_data["table_elements"].extend(page_tables)
                tables_data["pages"][str(page_idx)] = {
                    "tables": page_tables,
                    "table_count": len(page_tables)
                }
        
        tables_data["total_tables"] = len(tables_data["table_elements"])
        
        return tables_data
    
    def extract_images(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract images from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted image data
        """
        parsed_data = self.parse_pdf()
        
        images_data = {
            "total_pages": len(parsed_data['pages']),
            "image_elements": [],
            "pages": {},
            "total_images": 0,
            "saved_images": []
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(parsed_data['pages']))
        
        for page_idx in pages_to_process:
            if 0 <= page_idx < len(parsed_data['pages']):
                page = parsed_data['pages'][page_idx]
                sanitized_page = page['sanitized']
                
                page_images = []
                
                # Extract images from the sanitized page
                if 'images' in sanitized_page:
                    for img_idx, img in enumerate(sanitized_page['images']):
                        try:
                            image_element = {
                                "element_index": img_idx,
                                "page": page_idx,
                                "bbox": img.get('bbox', None),
                                "metadata": img.get('metadata', {}),
                                "width": img.get('width', 0),
                                "height": img.get('height', 0),
                                "format": img.get('format', 'unknown'),
                                "size_bytes": img.get('size_bytes', 0)
                            }
                            
                            # Try to save image if output directory is set and image data is available
                            if self.output_dir and 'data' in img:
                                try:
                                    img_filename = f"page_{page_idx + 1}_img_{img_idx + 1}.png"
                                    img_path = self.output_dir / img_filename
                                    
                                    # Save image data
                                    with open(img_path, 'wb') as f:
                                        f.write(img['data'])
                                    
                                    image_element["saved_path"] = str(img_path)
                                    images_data["saved_images"].append(str(img_path))
                                    
                                except Exception as e:
                                    print(f"Warning: Could not save image {img_idx} from page {page_idx}: {e}")
                            
                            page_images.append(image_element)
                            
                        except Exception as e:
                            print(f"Warning: Could not process image {img_idx} from page {page_idx}: {e}")
                            continue
                
                images_data["image_elements"].extend(page_images)
                images_data["pages"][str(page_idx)] = {
                    "images": page_images,
                    "image_count": len(page_images)
                }
        
        images_data["total_images"] = len(images_data["image_elements"])
        
        return images_data
    
    def extract_all(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract text, tables, and images from PDF
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing all extracted data
        """
        print("Parsing PDF with Docling...")
        parsed_data = self.parse_pdf()
        
        print("Extracting text...")
        text_data = self.extract_text(page_numbers)
        
        print("Extracting tables...")
        tables_data = self.extract_tables(page_numbers)
        
        print("Extracting images...")
        images_data = self.extract_images(page_numbers)
        
        return {
            "pdf_info": {
                "filename": self.pdf_path.name,
                "total_pages": len(parsed_data['pages']),
                "pages_processed": list(page_numbers) if page_numbers else "all"
            },
            "text": text_data,
            "tables": tables_data,
            "images": images_data,
            "raw_parsed_data": parsed_data  # Include raw data for advanced processing
        }
    
    def save_results(self, data: Dict[str, Any], filename_prefix: str = "docling_extraction"):
        """
        Save extraction results to files
        
        Args:
            data: Extracted data dictionary
            filename_prefix: Prefix for output files
        """
        if not self.output_dir:
            print("No output directory set. Results will only be returned.")
            return
        
        # Save text
        if "text" in data:
            text_file = self.output_dir / f"{filename_prefix}_text.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(data["text"]["full_text"])
            print(f"Text saved to: {text_file}")
        
        # Save tables as JSON
        if "tables" in data:
            tables_file = self.output_dir / f"{filename_prefix}_tables.json"
            with open(tables_file, 'w', encoding='utf-8') as f:
                json.dump(data["tables"], f, indent=2, ensure_ascii=False)
            print(f"Tables saved to: {tables_file}")
        
        # Save images info as JSON
        if "images" in data:
            images_file = self.output_dir / f"{filename_prefix}_images.json"
            with open(images_file, 'w', encoding='utf-8') as f:
                json.dump(data["images"], f, indent=2, ensure_ascii=False)
            print(f"Images info saved to: {images_file}")
        
        # Save complete results
        complete_file = self.output_dir / f"{filename_prefix}_complete.json"
        with open(complete_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Complete results saved to: {complete_file}")
        
        # Save raw parsed data
        raw_file = self.output_dir / f"{filename_prefix}_raw_data.json"
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(data.get("raw_parsed_data", []), f, indent=2, ensure_ascii=False)
        print(f"Raw parsed data saved to: {raw_file}")


def main():
    """Command-line interface for PDF extraction"""
    parser = argparse.ArgumentParser(
        description="Extract text, tables, and images from PDF files using Docling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_extractor_docling.py document.pdf --extract-all --output-dir ./output
  python pdf_extractor_docling.py document.pdf --extract-text --pages 0 1 2
  python pdf_extractor_docling.py document.pdf --extract-tables --output-dir ./tables
  python pdf_extractor_docling.py document.pdf --extract-images --output-dir ./images
        """
    )
    
    parser.add_argument("pdf_file", help="Path to the PDF file to process")
    parser.add_argument("--output-dir", "-o", help="Output directory for extracted content")
    parser.add_argument("--pages", "-p", nargs="+", type=int, 
                       help="Specific page numbers to process (0-indexed)")
    
    # Extraction options
    parser.add_argument("--extract-all", action="store_true", 
                       help="Extract text, tables, and images")
    parser.add_argument("--extract-text", action="store_true", 
                       help="Extract text only")
    parser.add_argument("--extract-tables", action="store_true", 
                       help="Extract tables only")
    parser.add_argument("--extract-images", action="store_true", 
                       help="Extract images only")
    
    # Output options
    parser.add_argument("--save-results", action="store_true", 
                       help="Save results to files")
    parser.add_argument("--print-summary", action="store_true", 
                       help="Print extraction summary")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.extract_all, args.extract_text, args.extract_tables, args.extract_images]):
        print("Error: Please specify what to extract (--extract-all, --extract-text, --extract-tables, or --extract-images)")
        sys.exit(1)
    
    try:
        # Initialize extractor
        extractor = DoclingPDFExtractor(args.pdf_file)
        
        # Set output directory
        if args.output_dir:
            extractor.set_output_directory(args.output_dir)
        
        # Process pages
        pages = args.pages if args.pages else None
        
        # Extract content based on options
        if args.extract_all:
            print(f"Extracting all content from {args.pdf_file} using Docling...")
            results = extractor.extract_all(pages)
            
        elif args.extract_text:
            print(f"Extracting text from {args.pdf_file} using Docling...")
            results = {"text": extractor.extract_text(pages)}
            
        elif args.extract_tables:
            print(f"Extracting tables from {args.pdf_file} using Docling...")
            results = {"tables": extractor.extract_tables(pages)}
            
        elif args.extract_images:
            print(f"Extracting images from {args.pdf_file} using Docling...")
            results = {"images": extractor.extract_images(pages)}
        
        # Save results if requested
        if args.save_results and args.output_dir:
            extractor.save_results(results)
        
        # Print summary if requested
        if args.print_summary:
            print("\n" + "="*50)
            print("DOCLING EXTRACTION SUMMARY")
            print("="*50)
            
            if "text" in results:
                text_data = results["text"]
                print(f"Text: {text_data['total_pages']} pages processed")
                total_chars = sum(element["char_count"] for element in text_data["text_elements"])
                total_words = sum(element["word_count"] for element in text_data["text_elements"])
                print(f"  Total characters: {total_chars:,}")
                print(f"  Total words: {total_words:,}")
                print(f"  Text elements: {len(text_data['text_elements'])}")
            
            if "tables" in results:
                tables_data = results["tables"]
                print(f"Tables: {tables_data['total_tables']} tables found")
                for page_num, page_data in tables_data["pages"].items():
                    if page_data["table_count"] > 0:
                        print(f"  Page {int(page_num) + 1}: {page_data['table_count']} tables")
            
            if "images" in results:
                images_data = results["images"]
                print(f"Images: {images_data['total_images']} images found")
                if images_data["saved_images"]:
                    print(f"  Saved {len(images_data['saved_images'])} images")
                for page_num, page_data in images_data["pages"].items():
                    if page_data["image_count"] > 0:
                        print(f"  Page {int(page_num) + 1}: {page_data['image_count']} images")
        
        print("\nDocling extraction completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
