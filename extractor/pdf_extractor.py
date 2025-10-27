#!/usr/bin/env python3
"""
PDF Text, Table, and Image Extractor using PyMuPDF (fitz)

This script extracts text, tables, and images from PDF files using PyMuPDF library.
It provides both programmatic and command-line interfaces for PDF processing.

Requirements:
    pip install PyMuPDF

Usage:
    python pdf_extractor.py input.pdf [--output-dir output_directory] [--extract-all]
    python pdf_extractor.py input.pdf --extract-text
    python pdf_extractor.py input.pdf --extract-tables
    python pdf_extractor.py input.pdf --extract-images
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF is not installed. Please install it using: pip install PyMuPDF")
    sys.exit(1)


class PDFExtractor:
    """PDF extraction class using PyMuPDF"""
    
    def __init__(self, pdf_path: str):
        """
        Initialize PDF extractor
        
        Args:
            pdf_path: Path to the PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.doc = fitz.open(str(self.pdf_path))
        self.output_dir = None
        
    def set_output_directory(self, output_dir: str):
        """Set output directory for extracted content"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_text(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract text from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted text data
        """
        text_data = {
            "total_pages": len(self.doc),
            "pages": {},
            "full_text": ""
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(self.doc))
        
        for page_num in pages_to_process:
            if 0 <= page_num < len(self.doc):
                page = self.doc[page_num]
                text = page.get_text()
                
                text_data["pages"][page_num] = {
                    "text": text,
                    "char_count": len(text),
                    "word_count": len(text.split())
                }
                text_data["full_text"] += f"\n--- Page {page_num + 1} ---\n{text}"
        
        return text_data
    
    def extract_tables(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract tables from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted table data
        """
        tables_data = {
            "total_pages": len(self.doc),
            "pages": {},
            "total_tables": 0
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(self.doc))
        
        for page_num in pages_to_process:
            if 0 <= page_num < len(self.doc):
                page = self.doc[page_num]
                tables = page.find_tables()
                
                page_tables = []
                for i, table in enumerate(tables):
                    try:
                        # Extract table data
                        table_data = table.extract()
                        if table_data:  # Only include non-empty tables
                            page_tables.append({
                                "table_index": i,
                                "bbox": table.bbox,  # Bounding box coordinates
                                "rows": len(table_data),
                                "cols": len(table_data[0]) if table_data else 0,
                                "data": table_data
                            })
                    except Exception as e:
                        print(f"Warning: Could not extract table {i} from page {page_num}: {e}")
                        continue
                
                tables_data["pages"][page_num] = {
                    "tables": page_tables,
                    "table_count": len(page_tables)
                }
                tables_data["total_tables"] += len(page_tables)
        
        return tables_data
    
    def extract_images(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract images from PDF pages
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing extracted image data
        """
        images_data = {
            "total_pages": len(self.doc),
            "pages": {},
            "total_images": 0,
            "saved_images": []
        }
        
        pages_to_process = page_numbers if page_numbers is not None else range(len(self.doc))
        
        for page_num in pages_to_process:
            if 0 <= page_num < len(self.doc):
                page = self.doc[page_num]
                image_list = page.get_images()
                
                page_images = []
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        pix = fitz.Pixmap(self.doc, xref)
                        
                        # Skip if image is too small (likely decorative)
                        if pix.width < 50 or pix.height < 50:
                            pix = None
                            continue
                        
                        # Convert to RGB if necessary
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = {
                                "image_index": img_index,
                                "xref": xref,
                                "width": pix.width,
                                "height": pix.height,
                                "colorspace": pix.colorspace.name if pix.colorspace else "Unknown",
                                "alpha": pix.alpha,
                                "size_bytes": len(pix.tobytes())
                            }
                            
                            # Save image if output directory is set
                            if self.output_dir:
                                img_filename = f"page_{page_num + 1}_img_{img_index + 1}.png"
                                img_path = self.output_dir / img_filename
                                pix.save(str(img_path))
                                img_data["saved_path"] = str(img_path)
                                images_data["saved_images"].append(str(img_path))
                            
                            page_images.append(img_data)
                        
                        pix = None  # Free memory
                        
                    except Exception as e:
                        print(f"Warning: Could not extract image {img_index} from page {page_num}: {e}")
                        continue
                
                images_data["pages"][page_num] = {
                    "images": page_images,
                    "image_count": len(page_images)
                }
                images_data["total_images"] += len(page_images)
        
        return images_data
    
    def extract_all(self, page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Extract text, tables, and images from PDF
        
        Args:
            page_numbers: List of page numbers to extract (0-indexed). If None, extracts all pages.
            
        Returns:
            Dictionary containing all extracted data
        """
        print("Extracting text...")
        text_data = self.extract_text(page_numbers)
        
        print("Extracting tables...")
        tables_data = self.extract_tables(page_numbers)
        
        print("Extracting images...")
        images_data = self.extract_images(page_numbers)
        
        return {
            "pdf_info": {
                "filename": self.pdf_path.name,
                "total_pages": len(self.doc),
                "pages_processed": list(page_numbers) if page_numbers else list(range(len(self.doc)))
            },
            "text": text_data,
            "tables": tables_data,
            "images": images_data
        }
    
    def save_results(self, data: Dict[str, Any], filename_prefix: str = "extraction"):
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
    
    def close(self):
        """Close the PDF document"""
        if hasattr(self, 'doc'):
            self.doc.close()


def main():
    """Command-line interface for PDF extraction"""
    parser = argparse.ArgumentParser(
        description="Extract text, tables, and images from PDF files using PyMuPDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_extractor.py document.pdf --extract-all --output-dir ./output
  python pdf_extractor.py document.pdf --extract-text --pages 0 1 2
  python pdf_extractor.py document.pdf --extract-tables --output-dir ./tables
  python pdf_extractor.py document.pdf --extract-images --output-dir ./images
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
        extractor = PDFExtractor(args.pdf_file)
        
        # Set output directory
        if args.output_dir:
            extractor.set_output_directory(args.output_dir)
        
        # Process pages
        pages = args.pages if args.pages else None
        
        # Extract content based on options
        if args.extract_all:
            print(f"Extracting all content from {args.pdf_file}...")
            results = extractor.extract_all(pages)
            
        elif args.extract_text:
            print(f"Extracting text from {args.pdf_file}...")
            results = {"text": extractor.extract_text(pages)}
            
        elif args.extract_tables:
            print(f"Extracting tables from {args.pdf_file}...")
            results = {"tables": extractor.extract_tables(pages)}
            
        elif args.extract_images:
            print(f"Extracting images from {args.pdf_file}...")
            results = {"images": extractor.extract_images(pages)}
        
        # Save results if requested
        if args.save_results and args.output_dir:
            extractor.save_results(results)
        
        # Print summary if requested
        if args.print_summary:
            print("\n" + "="*50)
            print("EXTRACTION SUMMARY")
            print("="*50)
            
            if "text" in results:
                text_data = results["text"]
                print(f"Text: {text_data['total_pages']} pages processed")
                total_chars = sum(page["char_count"] for page in text_data["pages"].values())
                total_words = sum(page["word_count"] for page in text_data["pages"].values())
                print(f"  Total characters: {total_chars:,}")
                print(f"  Total words: {total_words:,}")
            
            if "tables" in results:
                tables_data = results["tables"]
                print(f"Tables: {tables_data['total_tables']} tables found")
                for page_num, page_data in tables_data["pages"].items():
                    if page_data["table_count"] > 0:
                        print(f"  Page {page_num + 1}: {page_data['table_count']} tables")
            
            if "images" in results:
                images_data = results["images"]
                print(f"Images: {images_data['total_images']} images found")
                if images_data["saved_images"]:
                    print(f"  Saved {len(images_data['saved_images'])} images")
                for page_num, page_data in images_data["pages"].items():
                    if page_data["image_count"] > 0:
                        print(f"  Page {page_num + 1}: {page_data['image_count']} images")
        
        # Close document
        extractor.close()
        
        print("\nExtraction completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
