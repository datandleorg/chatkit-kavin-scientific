# MCP Quote Generator Server

This MCP (Model Context Protocol) server provides a tool to generate Excel quotes for products using a template file.

## Features

- Generate Excel quotes from product data
- Uses a template file (`quote.xlsx`) from Downloads folder
- Calculates tax amounts and totals automatically
- Auto-adjusts column widths for better readability
- Adds timestamps to generated quotes

## Installation

1. Install the required dependencies:
```bash
pip install -r mcp_requirements.txt
```

2. Ensure the template file exists at: `/Users/saravanan/Downloads/quote.xlsx`

## Usage

### Tool: `generate_quote_for_products`

Generates an Excel quote for a list of products.

**Parameters:**
- `products` (array): List of product objects with the following required fields:
  - `name` (string): Product name
  - `cas_number` (string): CAS (Chemical Abstracts Service) number
  - `packing` (string): Product packing information
  - `price` (number): Product price
  - `part` (string): Product part number or identifier
  - `hs_code` (string): Harmonized System Code
  - `tax` (number): Tax rate (percentage)
- `file_name` (string): Desired filename for the generated Excel quote

**Example:**
```json
{
  "products": [
    {
      "name": "Sodium Chloride",
      "cas_number": "7647-14-5",
      "packing": "25kg bag",
      "price": 50.00,
      "part": "SC-001",
      "hs_code": "2501.00.00",
      "tax": 18.0
    }
  ],
  "file_name": "chemical_quote_2024"
}
```

## Running the MCP Server

### Method 1: Stdio Mode (for local use)
```bash
python mcp_server.py
```

### Method 2: HTTP Mode (for remote connections)
```bash
python mcp_server.py --http --host 0.0.0.0 --port 8000
```

**Connection URL:** `http://localhost:8000/sse`

**Options:**
- `--http`: Enable HTTP mode
- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8000)

### Method 3: Using MCP configuration (stdio mode)
Add the server configuration to your MCP client's config file:

```json
{
  "mcpServers": {
    "quote-generator": {
      "command": "python",
      "args": ["/Users/saravanan/openai-agentkit-demo/mcp/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/saravanan/openai-agentkit-demo"
      }
    }
  }
}
```

### Method 4: Using MCP configuration (HTTP mode)
For HTTP connections, configure your MCP client with:

```json
{
  "mcpServers": {
    "quote-generator": {
      "url": "http://localhost:8000/sse",
      "transport": "sse"
    }
  }
}
```

## Testing

Run the test script to verify everything works:
```bash
python test_mcp_server.py
```

## Output

Generated Excel files are saved to the Downloads folder with the specified filename (automatically adds .xlsx extension if not provided).

## Error Handling

The server includes comprehensive error handling for:
- Missing template file
- Invalid product data
- Missing required fields
- File I/O errors

## Template Requirements

The template Excel file should have:
- Headers in the first row (or a row containing keywords like "S.No", "Product", etc.)
- Columns for: Serial Number, Product Name, CAS Number, Packing, Part Number, HS Code, Price, Tax Rate, Tax Amount, Total Price
- The server will automatically detect the data start row and fill in product information

## Important Notes

### Content Preservation
**Note:** The MCP server preserves most template content but may lose some complex elements during processing. The server uses the following approach to minimize data loss:

1. **Template Copying**: The original template is copied first to preserve structure
2. **Selective Modification**: Only product data cells are modified, leaving headers, formatting, and signatures intact
3. **Merged Cell Protection**: Merged cells are identified and protected from modification

### What Gets Preserved
✅ **Preserved Elements:**
- Headers and column formatting
- Merged cells (3 ranges detected in template)
- Basic cell formatting and styles
- Signatures and text content
- Worksheet structure

❌ **May Be Lost:**
- Complex embedded objects
- Advanced charts and graphics
- Some conditional formatting
- VBA macros (if present)

### File Size Analysis
- Original template: ~97KB (contains complex formatting/objects)
- Generated quote: ~7KB (data-focused version)
- Difference: ~89KB (complex elements not preserved by openpyxl)

### Recommendations
1. **Test with your template** to see what gets preserved
2. **Use the analysis script** (`image_restore_helper.py`) to understand what's in your template
3. **Consider manual post-processing** for critical visual elements
4. **Design templates** with minimal complex objects in the data area
