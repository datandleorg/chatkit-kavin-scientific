import os
import json
import csv
from docling_parse.pdf_parser import pdf_parser_v2

def extract_tables_from_pdf(pdf_path, output_dir="table_output"):
    """
    Extract only tables from PDF and save them to structured files
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted tables
    """
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🔍 Parsing PDF: {pdf_path}")
    print(f"📁 Output directory: {output_dir}/")
    
    # Create parser and load document
    parser = pdf_parser_v2(pdf_path)
    parser.load_document('doc1', pdf_path)
    
    # Parse the PDF
    result = parser.parse_pdf_from_key('doc1')
    
    print(f"📄 Parsed {len(result['pages'])} pages")
    
    # Extract tables from all pages
    all_tables = []
    table_count = 0
    
    for page_idx, page in enumerate(result['pages']):
        print(f"Processing page {page_idx + 1}/{len(result['pages'])}...")
        
        sanitized_page = page['sanitized']
        page_tables = []
        
        # Extract tables from cells (group cells by table structure)
        if 'cells' in sanitized_page and 'data' in sanitized_page['cells']:
            cells_data = sanitized_page['cells']['data']
            if cells_data:
                # Group cells that might form tables based on their positions
                table_groups = {}
                
                for cell_idx, cell_data in enumerate(cells_data):
                    if len(cell_data) > 12 and cell_data[12]:  # Check if text exists
                        cell_text = str(cell_data[12]).strip()
                        if cell_text:
                            # Extract bounding box coordinates
                            x0, y0, x1, y1 = cell_data[0], cell_data[1], cell_data[2], cell_data[3]
                            
                            # Group cells by similar y-coordinates (rows)
                            # Use a tolerance of 5 pixels for row grouping
                            row_key = round(y0 / 5) * 5
                            
                            if row_key not in table_groups:
                                table_groups[row_key] = []
                            
                            table_groups[row_key].append({
                                'text': cell_text,
                                'bbox': [x0, y0, x1, y1],
                                'cell_index': cell_idx,
                                'row_y': y0
                            })
                
                # Convert grouped cells into table structures
                if table_groups:
                    # Sort rows by y-coordinate
                    sorted_rows = sorted(table_groups.items(), key=lambda x: x[0])
                    
                    # Create table structure
                    table_data = []
                    for row_y, cells_in_row in sorted_rows:
                        # Sort cells in row by x-coordinate
                        sorted_cells = sorted(cells_in_row, key=lambda x: x['bbox'][0])
                        row_data = [cell['text'] for cell in sorted_cells]
                        table_data.append(row_data)
                    
                    # Only consider it a table if it has at least 2 rows and 2 columns
                    if len(table_data) >= 2 and all(len(row) >= 2 for row in table_data):
                        table_info = {
                            'table_id': f"table_{table_count + 1}",
                            'page_number': page_idx + 1,
                            'rows': len(table_data),
                            'columns': max(len(row) for row in table_data) if table_data else 0,
                            'data': table_data,
                            'bbox': {
                                'x0': min(cell['bbox'][0] for row in table_groups.values() for cell in row),
                                'y0': min(cell['bbox'][1] for row in table_groups.values() for cell in row),
                                'x1': max(cell['bbox'][2] for row in table_groups.values() for cell in row),
                                'y1': max(cell['bbox'][3] for row in table_groups.values() for cell in row)
                            }
                        }
                        
                        page_tables.append(table_info)
                        all_tables.append(table_info)
                        table_count += 1
        
        # Save individual page tables
        if page_tables:
            with open(f"{output_dir}/page_{page_idx + 1}_tables.json", 'w', encoding='utf-8') as f:
                json.dump({
                    'page_number': page_idx + 1,
                    'tables': page_tables
                }, f, indent=2, ensure_ascii=False)
            
            # Save as CSV files
            for table in page_tables:
                csv_filename = f"{output_dir}/page_{page_idx + 1}_{table['table_id']}.csv"
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for row in table['data']:
                        writer.writerow(row)
    
    # Save complete tables summary
    summary = {
        'total_tables': len(all_tables),
        'total_pages': len(result['pages']),
        'tables_per_page': {},
        'document_info': result['info']
    }
    
    # Count tables per page
    for table in all_tables:
        page_num = table['page_number']
        if page_num not in summary['tables_per_page']:
            summary['tables_per_page'][page_num] = 0
        summary['tables_per_page'][page_num] += 1
    
    with open(f"{output_dir}/tables_summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    # Save all tables in one file
    with open(f"{output_dir}/all_tables.json", 'w', encoding='utf-8') as f:
        json.dump(all_tables, f, indent=2, ensure_ascii=False)
    
    # Create a master CSV with all tables
    with open(f"{output_dir}/all_tables.csv", 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Table ID', 'Page', 'Row', 'Column', 'Value'])
        
        for table in all_tables:
            for row_idx, row_data in enumerate(table['data']):
                for col_idx, cell_value in enumerate(row_data):
                    writer.writerow([
                        table['table_id'],
                        table['page_number'],
                        row_idx + 1,
                        col_idx + 1,
                        cell_value
                    ])
    
    print(f"\n✅ Table extraction completed!")
    print(f"📁 Output saved to: {output_dir}/")
    print(f"📊 Summary:")
    print(f"   - Total tables found: {len(all_tables)}")
    print(f"   - Total pages processed: {len(result['pages'])}")
    print(f"   - Tables per page: {dict(list(summary['tables_per_page'].items())[:10])}...")
    
    print(f"\n📄 Files created:")
    print(f"   - tables_summary.json (extraction statistics)")
    print(f"   - all_tables.json (all tables in JSON format)")
    print(f"   - all_tables.csv (all tables in CSV format)")
    print(f"   - page_X_tables.json (tables per page)")
    print(f"   - page_X_table_Y.csv (individual table CSV files)")
    
    return all_tables

if __name__ == "__main__":
    # Configuration
    pdf_path = "test.pdf"
    output_dir = "table_output"
    
    # Extract tables
    tables = extract_tables_from_pdf(pdf_path, output_dir)
    
    # Show sample of first table
    if tables:
        print(f"\n📋 Sample of first table:")
        print(f"   Table ID: {tables[0]['table_id']}")
        print(f"   Page: {tables[0]['page_number']}")
        print(f"   Size: {tables[0]['rows']} rows × {tables[0]['columns']} columns")
        print(f"   First few rows:")
        for i, row in enumerate(tables[0]['data'][:3]):
            print(f"     Row {i+1}: {row[:5]}...")  # Show first 5 columns
