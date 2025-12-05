import os
import json
from docling_parse.pdf_parser import pdf_parser_v2

# Input PDF and output directory
pdf_path = "test.pdf"
output_dir = "extracted_output"

# Create output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# Create parser and load document
parser = pdf_parser_v2(pdf_path)
parser.load_document('doc1', pdf_path)

# Parse the PDF
result = parser.parse_pdf_from_key('doc1')

print(f"Parsed {len(result['pages'])} pages")
print(f"Document info: {result['info']}")
print(f"Extracting content to: {output_dir}/")

# Save document info
with open(f"{output_dir}/document_info.json", 'w') as f:
    json.dump(result['info'], f, indent=2)

# Extract content from all pages
all_text_content = []
all_tables = []
all_images = []

for page_idx, page in enumerate(result['pages']):
    print(f"Processing page {page_idx + 1}/{len(result['pages'])}...")
    
    sanitized_page = page['sanitized']
    page_content = {
        "page_number": page_idx + 1,
        "cells": [],
        "lines": [],
        "images": []
    }
    
    # Extract text from cells
    if 'cells' in sanitized_page and 'data' in sanitized_page['cells']:
        cells_data = sanitized_page['cells']['data']
        for cell_idx, cell_data in enumerate(cells_data):
            if len(cell_data) > 12 and cell_data[12]:
                cell_text = str(cell_data[12])
                if cell_text.strip():
                    cell_info = {
                        "cell_index": cell_idx,
                        "text": cell_text,
                        "bbox": cell_data[:4] if len(cell_data) >= 4 else None
                    }
                    page_content["cells"].append(cell_info)
                    all_text_content.append(cell_text)
    
    # Extract text from lines
    if 'lines' in sanitized_page:
        lines_data = sanitized_page['lines']
        for line_idx, line in enumerate(lines_data):
            if hasattr(line, 'text') and line.text and line.text.strip():
                line_info = {
                    "line_index": line_idx,
                    "text": line.text,
                    "bbox": getattr(line, 'bbox', None)
                }
                page_content["lines"].append(line_info)
                all_text_content.append(line.text)
    
    # Extract images info
    if 'images' in sanitized_page:
        images_data = sanitized_page['images']
        for img_idx, img in enumerate(images_data):
            img_info = {
                "image_index": img_idx,
                "page": page_idx + 1
            }
            page_content["images"].append(img_info)
            all_images.append(img_info)
    
    # Save individual page content
    with open(f"{output_dir}/page_{page_idx + 1}.json", 'w') as f:
        json.dump(page_content, f, indent=2)
    
    # Save page text content
    page_text = "\n".join([cell["text"] for cell in page_content["cells"]]) + "\n" + "\n".join([line["text"] for line in page_content["lines"]])
    with open(f"{output_dir}/page_{page_idx + 1}.txt", 'w', encoding='utf-8') as f:
        f.write(page_text)

# Save complete text content
complete_text = "\n".join(all_text_content)
with open(f"{output_dir}/complete_text.txt", 'w', encoding='utf-8') as f:
    f.write(complete_text)

# Save summary
summary = {
    "total_pages": len(result['pages']),
    "total_cells": sum(len(page['sanitized'].get('cells', {}).get('data', [])) for page in result['pages']),
    "total_lines": sum(len(page['sanitized'].get('lines', [])) for page in result['pages']),
    "total_images": len(all_images),
    "total_text_elements": len(all_text_content),
    "document_info": result['info']
}

with open(f"{output_dir}/extraction_summary.json", 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\n✅ Extraction completed!")
print(f"📁 Output saved to: {output_dir}/")
print(f"📄 Files created:")
print(f"   - document_info.json (document metadata)")
print(f"   - extraction_summary.json (extraction statistics)")
print(f"   - complete_text.txt (all text content)")
print(f"   - page_X.json (individual page data)")
print(f"   - page_X.txt (individual page text)")
print(f"\n📊 Summary:")
print(f"   - Total pages: {summary['total_pages']}")
print(f"   - Total cells: {summary['total_cells']}")
print(f"   - Total lines: {summary['total_lines']}")
print(f"   - Total images: {summary['total_images']}")
print(f"   - Total text elements: {summary['total_text_elements']}")
