# Docling PDF Extractor Documentation

## Overview
This Python script extracts text, tables, and images from PDF files using Docling, a modern PDF processing library that provides advanced document understanding capabilities. Docling offers superior table detection and structured content extraction compared to traditional libraries.

## Installation

1. Install required packages:
```bash
pip install docling-parse pillow
```

Or install from requirements:
```bash
pip install -r requirements.txt
```

## Features

- **Advanced Text Extraction**: Extract text with element-level granularity and metadata
- **Superior Table Detection**: Better table recognition and extraction with Docling's AI-powered processing
- **Image Extraction**: Extract images with metadata and automatic format conversion
- **Structured Content**: Access to raw parsed data with element types and bounding boxes
- **Flexible Page Selection**: Process specific pages or all pages
- **Multiple Output Formats**: Save results as text files, JSON, and images
- **Command-line Interface**: Easy-to-use CLI with various options
- **Programmatic API**: Use the DoclingPDFExtractor class in your own scripts

## Key Advantages of Docling

- **AI-Powered Processing**: Uses machine learning for better document understanding
- **Element-Level Granularity**: Access to individual document elements (paragraphs, headings, etc.)
- **Better Table Detection**: Superior table recognition compared to traditional libraries
- **Structured Output**: Rich metadata including element types, bounding boxes, and page information
- **Modern Architecture**: Built for modern document processing workflows

## Usage

### Command Line Interface

#### Extract everything from a PDF:
```bash
python pdf_extractor_docling.py document.pdf --extract-all --output-dir ./output
```

#### Extract only text:
```bash
python pdf_extractor_docling.py document.pdf --extract-text --output-dir ./text_output
```

#### Extract only tables:
```bash
python pdf_extractor_docling.py document.pdf --extract-tables --output-dir ./tables_output
```

#### Extract only images:
```bash
python pdf_extractor_docling.py document.pdf --extract-images --output-dir ./images_output
```

#### Process specific pages:
```bash
python pdf_extractor_docling.py document.pdf --extract-all --pages 0 1 2 --output-dir ./output
```

#### Save results and print summary:
```bash
python pdf_extractor_docling.py document.pdf --extract-all --save-results --print-summary --output-dir ./output
```

### Programmatic Usage

```python
from pdf_extractor_docling import DoclingPDFExtractor

# Initialize extractor
extractor = DoclingPDFExtractor("document.pdf")

# Set output directory
extractor.set_output_directory("./output")

# Parse PDF (optional - done automatically)
parsed_data = extractor.parse_pdf()

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
```

## Output Files

When using the `--save-results` option, the script creates:

- `docling_extraction_text.txt`: Plain text content
- `docling_extraction_tables.json`: Table data in JSON format
- `docling_extraction_images.json`: Image metadata in JSON format
- `docling_extraction_complete.json`: Complete extraction results
- `docling_extraction_raw_data.json`: Raw parsed data from Docling
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
  "total_elements": 150,
  "text_elements": [
    {
      "element_index": 0,
      "text": "Document Title",
      "char_count": 13,
      "word_count": 2,
      "page": 0,
      "element_type": "heading",
      "bbox": [100, 50, 400, 80]
    }
  ],
  "full_text": "Complete text content...",
  "pages": {
    "0": {
      "text": "Page text content...",
      "char_count": 1234,
      "word_count": 234
    }
  }
}
```

### Table Extraction
```json
{
  "total_elements": 150,
  "table_elements": [
    {
      "element_index": 25,
      "page": 1,
      "bbox": [100, 200, 400, 300],
      "rows": 3,
      "cols": 4,
      "data": [["Header1", "Header2", "Header3", "Header4"], ...],
      "metadata": {...}
    }
  ],
  "pages": {
    "1": {
      "tables": [...],
      "table_count": 1
    }
  },
  "total_tables": 1
}
```

### Image Extraction
```json
{
  "total_elements": 150,
  "image_elements": [
    {
      "element_index": 45,
      "page": 2,
      "width": 800,
      "height": 600,
      "format": "PNG",
      "mode": "RGB",
      "size_bytes": 1440000,
      "bbox": [50, 100, 850, 700],
      "metadata": {...},
      "saved_path": "./output/page_3_img_46.png"
    }
  ],
  "pages": {
    "2": {
      "images": [...],
      "image_count": 1
    }
  },
  "total_images": 1,
  "saved_images": ["./output/page_3_img_46.png"]
}
```

## Docling vs PyMuPDF Comparison

| Feature | Docling | PyMuPDF |
|---------|---------|---------|
| Text Extraction | Element-level with metadata | Page-level |
| Table Detection | AI-powered, superior | Basic pattern matching |
| Image Extraction | Rich metadata | Basic extraction |
| Processing Speed | Moderate | Fast |
| Memory Usage | Higher | Lower |
| Accuracy | High for complex docs | Good for simple docs |
| Element Types | Rich (headings, paragraphs, etc.) | Basic (text, tables, images) |

## Error Handling

The script includes comprehensive error handling:
- File not found errors
- Invalid page numbers
- Corrupted PDF files
- Image processing errors
- Memory management for large documents
- Graceful handling of extraction failures

## Performance Notes

- Docling uses AI processing, so it may be slower than traditional libraries
- Memory usage is higher due to the AI model
- Better accuracy for complex documents with tables and mixed content
- Processing can be limited to specific pages for better performance
- Images are automatically converted to RGB and saved as PNG

## Requirements

- Python 3.7+
- docling-parse >= 0.1.0
- Pillow >= 9.0.0

## Advanced Usage

### Accessing Raw Parsed Data
```python
extractor = DoclingPDFExtractor("document.pdf")
parsed_data = extractor.parse_pdf()

# Access individual elements
for element in parsed_data:
    print(f"Type: {element.get('type')}")
    print(f"Text: {element.get('text', '')[:100]}")
    print(f"Metadata: {element.get('metadata', {})}")
```

### Element Type Filtering
```python
# Extract only specific element types
text_data = extractor.extract_text()
headings = [elem for elem in text_data['text_elements'] if elem['element_type'] == 'heading']
paragraphs = [elem for elem in text_data['text_elements'] if elem['element_type'] == 'paragraph']
```

## Troubleshooting

### Common Issues

1. **Import Error**: Make sure docling-parse is installed
   ```bash
   pip install docling-parse pillow
   ```

2. **Memory Issues**: Process specific pages instead of entire document
   ```bash
   python pdf_extractor_docling.py document.pdf --extract-all --pages 0 1 2
   ```

3. **Slow Processing**: Docling uses AI, so it's naturally slower than traditional libraries

4. **No Tables Found**: Docling may detect tables differently - check the raw parsed data for element types
