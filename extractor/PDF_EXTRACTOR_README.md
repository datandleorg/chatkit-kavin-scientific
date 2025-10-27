# PDF Extractor Documentation

## Overview
This Python script extracts text, tables, and images from PDF files using PyMuPDF (fitz). It provides both programmatic and command-line interfaces for PDF processing.

## Installation

1. Install PyMuPDF:
```bash
pip install PyMuPDF
```

Or install from requirements:
```bash
pip install -r requirements_pdf.txt
```

## Features

- **Text Extraction**: Extract plain text from PDF pages with character and word counts
- **Table Extraction**: Detect and extract tabular data with bounding box information
- **Image Extraction**: Extract images and save them as PNG files
- **Flexible Page Selection**: Process specific pages or all pages
- **Multiple Output Formats**: Save results as text files, JSON, and images
- **Command-line Interface**: Easy-to-use CLI with various options
- **Programmatic API**: Use the PDFExtractor class in your own scripts

## Usage

### Command Line Interface

#### Extract everything from a PDF:
```bash
python pdf_extractor.py document.pdf --extract-all --output-dir ./output
```

#### Extract only text:
```bash
python pdf_extractor.py document.pdf --extract-text --output-dir ./text_output
```

#### Extract only tables:
```bash
python pdf_extractor.py document.pdf --extract-tables --output-dir ./tables_output
```

#### Extract only images:
```bash
python pdf_extractor.py document.pdf --extract-images --output-dir ./images_output
```

#### Process specific pages:
```bash
python pdf_extractor.py document.pdf --extract-all --pages 0 1 2 --output-dir ./output
```

#### Save results and print summary:
```bash
python pdf_extractor.py document.pdf --extract-all --save-results --print-summary --output-dir ./output
```

### Programmatic Usage

```python
from pdf_extractor import PDFExtractor

# Initialize extractor
extractor = PDFExtractor("document.pdf")

# Set output directory
extractor.set_output_directory("./output")

# Extract text
text_data = extractor.extract_text()

# Extract tables
tables_data = extractor.extract_tables()

# Extract images
images_data = extractor.extract_images()

# Extract everything
all_data = extractor.extract_all()

# Save results
extractor.save_results(all_data)

# Close document
extractor.close()
```

## Output Files

When using the `--save-results` option, the script creates:

- `extraction_text.txt`: Plain text content
- `extraction_tables.json`: Table data in JSON format
- `extraction_images.json`: Image metadata in JSON format
- `extraction_complete.json`: Complete extraction results
- `page_X_img_Y.png`: Extracted images

## Command Line Options

- `pdf_file`: Path to the PDF file to process (required)
- `--output-dir, -o`: Output directory for extracted content
- `--pages, -p`: Specific page numbers to process (0-indexed)
- `--extract-all`: Extract text, tables, and images
- `--extract-text`: Extract text only
- `--extract-tables`: Extract tables only
- `--extract-images`: Extract images only
- `--save-results`: Save results to files
- `--print-summary`: Print extraction summary

## Example Output

### Text Extraction
```json
{
  "total_pages": 5,
  "pages": {
    "0": {
      "text": "Sample text content...",
      "char_count": 1234,
      "word_count": 234
    }
  },
  "full_text": "Complete text content..."
}
```

### Table Extraction
```json
{
  "total_pages": 5,
  "pages": {
    "0": {
      "tables": [
        {
          "table_index": 0,
          "bbox": [100, 200, 400, 300],
          "rows": 3,
          "cols": 4,
          "data": [["Header1", "Header2", "Header3", "Header4"], ...]
        }
      ],
      "table_count": 1
    }
  },
  "total_tables": 1
}
```

### Image Extraction
```json
{
  "total_pages": 5,
  "pages": {
    "0": {
      "images": [
        {
          "image_index": 0,
          "xref": 123,
          "width": 800,
          "height": 600,
          "colorspace": "DeviceRGB",
          "alpha": 0,
          "size_bytes": 1440000,
          "saved_path": "./output/page_1_img_1.png"
        }
      ],
      "image_count": 1
    }
  },
  "total_images": 1,
  "saved_images": ["./output/page_1_img_1.png"]
}
```

## Error Handling

The script includes comprehensive error handling:
- File not found errors
- Invalid page numbers
- Corrupted PDF files
- Memory management for large images
- Graceful handling of extraction failures

## Performance Notes

- Large PDFs with many images may require significant memory
- Image extraction is automatically filtered to exclude very small images (< 50x50 pixels)
- Memory is freed after processing each image to prevent memory leaks
- Processing can be limited to specific pages for better performance

## Requirements

- Python 3.6+
- PyMuPDF (fitz) >= 1.23.0
