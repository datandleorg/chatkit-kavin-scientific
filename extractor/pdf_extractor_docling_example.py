#!/usr/bin/env python3
"""
Example usage of Docling PDF Extractor

This script demonstrates how to use the DoclingPDFExtractor class programmatically.
Docling provides advanced PDF processing with better table detection and
structured content extraction.
"""

from pdf_extractor_docling import DoclingPDFExtractor
import json

def example_usage():
    """Example of using DoclingPDFExtractor programmatically"""
    
    # Example PDF file path (replace with your actual PDF file)
    pdf_file = "test.pdf"
    
    try:
        # Initialize the extractor
        extractor = DoclingPDFExtractor(pdf_file)
        
        # Set output directory
        extractor.set_output_directory("./docling_output")
        
        print("=== Docling PDF Extraction Example ===")
        print(f"Processing: {pdf_file}")
        
        # Parse PDF first to get element count
        parsed_data = extractor.parse_pdf()
        print(f"Total elements found: {len(parsed_data)}")
        
        # Extract text from first few elements
        print("\n1. Extracting text...")
        text_data = extractor.extract_text()
        print(f"   Found {len(text_data['text_elements'])} text elements")
        print(f"   Total characters: {sum(element['char_count'] for element in text_data['text_elements'])}")
        print(f"   Total words: {sum(element['word_count'] for element in text_data['text_elements'])}")
        
        # Show text elements by type
        element_types = {}
        for element in text_data['text_elements']:
            elem_type = element['element_type']
            element_types[elem_type] = element_types.get(elem_type, 0) + 1
        
        print("   Text elements by type:")
        for elem_type, count in element_types.items():
            print(f"     {elem_type}: {count}")
        
        # Extract tables
        print("\n2. Extracting tables...")
        tables_data = extractor.extract_tables()
        print(f"   Found {tables_data['total_tables']} tables")
        
        # Show table details
        for table in tables_data['table_elements']:
            print(f"   Table {table['element_index']}: {table['rows']} rows x {table['cols']} cols (Page {table['page'] + 1})")
        
        # Extract images
        print("\n3. Extracting images...")
        images_data = extractor.extract_images()
        print(f"   Found {images_data['total_images']} images")
        
        # Show image details
        for img in images_data['image_elements']:
            print(f"   Image {img['element_index']}: {img['width']}x{img['height']} pixels, {img['format']} format (Page {img['page'] + 1})")
        
        # Extract everything
        print("\n4. Extracting all content...")
        all_data = extractor.extract_all()
        
        # Save results
        print("\n5. Saving results...")
        extractor.save_results(all_data, "docling_example")
        
        # Print sample text from first text element
        if text_data['text_elements']:
            first_text = text_data['text_elements'][0]['text']
            print(f"\n6. Sample text from first element (first 200 chars):")
            print("-" * 50)
            print(first_text[:200] + "..." if len(first_text) > 200 else first_text)
        
        # Show raw parsed data structure
        print(f"\n7. Raw parsed data structure:")
        print(f"   Total elements: {len(all_data['raw_parsed_data'])}")
        
        # Show element types in raw data
        raw_element_types = {}
        for element in all_data['raw_parsed_data']:
            elem_type = element.get('type', 'unknown')
            raw_element_types[elem_type] = raw_element_types.get(elem_type, 0) + 1
        
        print("   Element types in raw data:")
        for elem_type, count in raw_element_types.items():
            print(f"     {elem_type}: {count}")
        
        print("\n=== Docling extraction completed successfully! ===")
        
    except FileNotFoundError:
        print(f"Error: PDF file '{pdf_file}' not found.")
        print("Please provide a valid PDF file path.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def compare_with_pymupdf():
    """Compare Docling results with PyMuPDF results"""
    print("\n=== Comparing Docling vs PyMuPDF ===")
    
    pdf_file = "test.pdf"
    
    try:
        # Docling extraction
        print("Docling extraction:")
        docling_extractor = DoclingPDFExtractor(pdf_file)
        docling_results = docling_extractor.extract_all()
        
        print(f"  Elements: {docling_results['pdf_info']['total_elements']}")
        print(f"  Text elements: {len(docling_results['text']['text_elements'])}")
        print(f"  Tables: {docling_results['tables']['total_tables']}")
        print(f"  Images: {docling_results['images']['total_images']}")
        
        # PyMuPDF extraction (if available)
        try:
            from pdf_extractor import PDFExtractor
            print("\nPyMuPDF extraction:")
            pymupdf_extractor = PDFExtractor(pdf_file)
            pymupdf_results = pymupdf_extractor.extract_all()
            
            print(f"  Pages: {pymupdf_results['pdf_info']['total_pages']}")
            print(f"  Text pages: {len(pymupdf_results['text']['pages'])}")
            print(f"  Tables: {pymupdf_results['tables']['total_tables']}")
            print(f"  Images: {pymupdf_results['images']['total_images']}")
            
            pymupdf_extractor.close()
            
        except ImportError:
            print("\nPyMuPDF extractor not available for comparison")
        
    except Exception as e:
        print(f"Error in comparison: {e}")

if __name__ == "__main__":
    example_usage()
    compare_with_pymupdf()
