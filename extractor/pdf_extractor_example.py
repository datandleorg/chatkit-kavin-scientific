#!/usr/bin/env python3
"""
Example usage of PDF Extractor

This script demonstrates how to use the PDFExtractor class programmatically.
"""

from pdf_extractor import PDFExtractor
import json

def example_usage():
    """Example of using PDFExtractor programmatically"""
    
    # Example PDF file path (replace with your actual PDF file)
    pdf_file = "example.pdf"
    
    try:
        # Initialize the extractor
        extractor = PDFExtractor(pdf_file)
        
        # Set output directory
        extractor.set_output_directory("./extracted_content")
        
        print("=== PDF Extraction Example ===")
        print(f"Processing: {pdf_file}")
        print(f"Total pages: {len(extractor.doc)}")
        
        # Extract text from first 3 pages
        print("\n1. Extracting text from first 3 pages...")
        text_data = extractor.extract_text([0, 1, 2])
        print(f"   Extracted text from {len(text_data['pages'])} pages")
        print(f"   Total characters: {sum(page['char_count'] for page in text_data['pages'].values())}")
        
        # Extract tables from all pages
        print("\n2. Extracting tables from all pages...")
        tables_data = extractor.extract_tables()
        print(f"   Found {tables_data['total_tables']} tables total")
        
        # Show table details for pages with tables
        for page_num, page_data in tables_data["pages"].items():
            if page_data["table_count"] > 0:
                print(f"   Page {page_num + 1}: {page_data['table_count']} tables")
                for table in page_data["tables"]:
                    print(f"     Table {table['table_index'] + 1}: {table['rows']} rows x {table['cols']} cols")
        
        # Extract images from all pages
        print("\n3. Extracting images from all pages...")
        images_data = extractor.extract_images()
        print(f"   Found {images_data['total_images']} images total")
        
        # Show image details for pages with images
        for page_num, page_data in images_data["pages"].items():
            if page_data["image_count"] > 0:
                print(f"   Page {page_num + 1}: {page_data['image_count']} images")
                for img in page_data["images"]:
                    print(f"     Image {img['image_index'] + 1}: {img['width']}x{img['height']} pixels")
        
        # Extract everything from specific pages
        print("\n4. Extracting everything from pages 0-2...")
        all_data = extractor.extract_all([0, 1, 2])
        
        # Save results
        print("\n5. Saving results...")
        extractor.save_results(all_data, "example_extraction")
        
        # Print a sample of extracted text
        if text_data["pages"]:
            first_page_text = list(text_data["pages"].values())[0]["text"]
            print(f"\n6. Sample text from first page (first 200 chars):")
            print("-" * 50)
            print(first_page_text[:200] + "..." if len(first_page_text) > 200 else first_page_text)
        
        # Close the document
        extractor.close()
        
        print("\n=== Extraction completed successfully! ===")
        
    except FileNotFoundError:
        print(f"Error: PDF file '{pdf_file}' not found.")
        print("Please provide a valid PDF file path.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    example_usage()
