#!/usr/bin/env python3
"""
XML-based Quote Generator
Directly manipulates Excel XML structure to preserve images while updating data.
No openpyxl dependency - pure ZIP/XML manipulation.
"""

import os
import shutil
import zipfile
import tempfile
import copy
from typing import List, Dict, Any
import xml.etree.ElementTree as ET

class XMLQuoteGenerator:
    """Generator that preserves ALL content including images by working with Excel XML."""
    
    # Excel XML namespace
    NS = {
        'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }
    
    def __init__(self, template_path: str):
        self.template_path = template_path
        
    def generate_quote(self, products: List[Dict[str, Any]], file_name: str) -> str:
        """
        Generate quote while preserving ALL images and content.
        Works by extracting Excel as ZIP, modifying XML, and recreating.
        """
        try:
            if not file_name.endswith('.xlsx'):
                file_name += '.xlsx'
            
            output_path = os.path.join("/Users/saravanan/kavin/chatkit-kavin-scientific/mcp", file_name)
            
            # Create temporary directory
            temp_dir = tempfile.mkdtemp()
            extracted_dir = os.path.join(temp_dir, "extracted")
            
            print(f"Extracting template to: {extracted_dir}")
            
            # Step 1: Extract the entire Excel file as a ZIP
            with zipfile.ZipFile(self.template_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_dir)
            
            # Step 2: Modify the worksheet XML to update product data
            self._update_worksheet_xml(extracted_dir, products)
            
            # Step 3: Recreate the Excel file with ALL original content
            print(f"Creating output file: {output_path}")
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, dirs, files in os.walk(extracted_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, extracted_dir)
                        zip_ref.write(file_path, arc_path)
            
            # Cleanup
            shutil.rmtree(temp_dir)
            
            print(f"✅ Quote generated with FULL preservation: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _update_worksheet_xml(self, extracted_dir: str, products: List[Dict[str, Any]]):
        """Update worksheet XML with new product data."""
        worksheet_path = os.path.join(extracted_dir, "xl", "worksheets", "sheet1.xml")
        
        if not os.path.exists(worksheet_path):
            print(f"Worksheet not found at: {worksheet_path}")
            return
        
        print(f"Updating worksheet: {worksheet_path}")
        
        # Register namespaces
        ET.register_namespace('', self.NS['main'])
        ET.register_namespace('r', self.NS['r'])
        
        # Parse the XML
        tree = ET.parse(worksheet_path)
        root = tree.getroot()
        
        # Find the sheetData element
        sheet_data = root.find(f'.//{{{self.NS["main"]}}}sheetData')
        
        if sheet_data is None:
            print("SheetData not found")
            return
        
        # Find and store ALL content after row 23 before clearing
        content_after_23 = self._extract_all_rows_after(sheet_data, 23)
        
        # Clear existing rows (rows 15-23)
        self._clear_product_rows(sheet_data, 15, 23)
        
        # Insert new product data and get the ending row
        last_product_row, total_gamt = self._insert_product_rows(sheet_data, products)
        
        # Insert total row
        total_row_num = last_product_row + 1
        self._insert_total_row(sheet_data, total_row_num, total_gamt)
        
        # Move all content after the total row
        if content_after_23:
            self._insert_moved_content(sheet_data, total_row_num + 1, content_after_23)
        
        # Write back to file with proper formatting
        tree.write(worksheet_path, encoding='utf-8', xml_declaration=True)
        print(f"Worksheet updated successfully")
    
    def _clear_product_rows(self, sheet_data, start_row: int, end_row: int):
        """Clear existing product data rows."""
        print(f"Clearing rows {start_row} to {end_row}")
        
        rows_to_remove = []
        for row in sheet_data.findall(f'.//{{{self.NS["main"]}}}row'):
            row_num = int(row.get('r', '0'))
            if start_row <= row_num <= end_row:
                rows_to_remove.append(row)
        
        for row in rows_to_remove:
            sheet_data.remove(row)
        
        print(f"Removed {len(rows_to_remove)} rows")
    
    def _insert_product_rows(self, sheet_data, products: List[Dict[str, Any]]) -> tuple:
        """Insert new product rows into the sheet. Returns (last_row_num, total_gamt)."""
        print(f"Inserting {len(products)} products")
        
        current_row = 15
        total_gamt = 0
        
        for i, product in enumerate(products, 1):
            # Extract and calculate product data
            sno = i
            name = product.get('name', '')
            catno = product.get('cas_number', '')
            hsn = product.get('hs_code', '')
            brand = product.get('part', '')
            unit = product.get('packing', '')
            rate = float(product.get('price', 0))
            dis = float(product.get('tax', 0)) / 100
            qty = 1
            gst = 0.18
            
            # Calculate derived fields
            discounted_rate = rate * (1 - dis)
            amount = discounted_rate * qty
            gval = amount * gst
            gamt = amount + gval
            total_gamt += gamt
            
            # Create row element
            row = self._create_row_element(current_row, sno, name, catno, hsn, brand, unit,
                                          rate, dis, discounted_rate, qty, amount, gst, gval, gamt)
            
            # Find the correct position to insert (maintain row order)
            self._insert_row_in_order(sheet_data, row, current_row)
            
            print(f"  Inserted product {i}: {name}")
            current_row += 1
        
        print(f"Total G.Amt: ${total_gamt:.2f}")
        return current_row - 1, total_gamt  # Return last row number and total
    
    def _create_row_element(self, row_num: int, sno, name, catno, hsn, brand, unit,
                           rate, dis, discounted_rate, qty, amount, gst, gval, gamt):
        """Create a row element with all product data."""
        row = ET.Element(f'{{{self.NS["main"]}}}row', r=str(row_num))
        
        # Add cells with proper types
        self._add_cell(row, 'A', row_num, sno, 'n')  # S.no (number)
        self._add_cell(row, 'B', row_num, name, 's')  # Name (string)
        self._add_cell(row, 'C', row_num, catno, 's')  # Cat.No (string)
        self._add_cell(row, 'D', row_num, hsn, 's')  # HSN (string)
        self._add_cell(row, 'E', row_num, brand, 's')  # Brand (string)
        self._add_cell(row, 'F', row_num, unit, 's')  # Unit (string)
        self._add_cell(row, 'G', row_num, rate, 'n')  # Rate (number)
        self._add_cell(row, 'H', row_num, dis, 'n')  # Discount (number)
        self._add_cell(row, 'I', row_num, discounted_rate, 'n')  # Discounted Rate (number)
        self._add_cell(row, 'J', row_num, qty, 'n')  # Qty (number)
        self._add_cell(row, 'K', row_num, amount, 'n')  # Amount (number)
        self._add_cell(row, 'L', row_num, gst, 'n')  # GST (number)
        self._add_cell(row, 'M', row_num, gval, 'n')  # G.Val (number)
        self._add_cell(row, 'N', row_num, gamt, 'n')  # G.Amt (number)
        
        return row
    
    def _add_cell(self, row, col_letter: str, row_num: int, value, cell_type: str = 's'):
        """Add a cell to a row element."""
        cell = ET.SubElement(row, f'{{{self.NS["main"]}}}c', r=f"{col_letter}{row_num}")
        
        if cell_type == 'n':  # Number
            cell.set('t', 'n')
            v = ET.SubElement(cell, f'{{{self.NS["main"]}}}v')
            v.text = str(value) if value is not None else '0'
        else:  # String (inline string)
            cell.set('t', 'inlineStr')
            is_elem = ET.SubElement(cell, f'{{{self.NS["main"]}}}is')
            t = ET.SubElement(is_elem, f'{{{self.NS["main"]}}}t')
            t.text = str(value) if value is not None else ''
    
    def _extract_all_rows_after(self, sheet_data, after_row: int) -> list:
        """Extract ALL rows after the specified row number."""
        rows_after = []
        print(f"Extracting all rows after row {after_row}...")
        
        for row in sheet_data.findall(f'.//{{{self.NS["main"]}}}row'):
            row_num = int(row.get('r', '0'))
            if row_num > after_row:  # All rows after the specified row
                # Deep copy the row to preserve it after clearing
                row_copy = copy.deepcopy(row)
                rows_after.append((row_num, row_copy))
        
        # Sort by original row number
        rows_after.sort(key=lambda x: x[0])
        print(f"Found {len(rows_after)} rows after row {after_row}")
        return rows_after
    
    def _insert_total_row(self, sheet_data, row_num: int, total_amount: float):
        """Insert a total row with summary information."""
        print(f"Inserting total row at row {row_num}")
        
        total_row = ET.Element(f'{{{self.NS["main"]}}}row', r=str(row_num))
        
        # Add cells for total row
        # Column A: "Total" label
        self._add_cell(total_row, 'A', row_num, 'TOTAL', 's')
        
        # Columns B-F: Empty or labels
        # Column N: Total grand amount
        self._add_cell(total_row, 'N', row_num, round(total_amount, 2), 'n')
        
        # Insert the total row
        self._insert_row_in_order(sheet_data, total_row, row_num)
    
    def _insert_moved_content(self, sheet_data, start_row: int, rows_data: list):
        """Insert moved content rows starting at the given row."""
        print(f"Inserting moved content starting at row {start_row}")
        
        current_row = start_row
        for original_row_num, row_element in rows_data:
            # Create a new row element
            new_row = ET.Element(row_element.tag)
            
            # Update row number
            new_row.set('r', str(current_row))
            
            # Copy and update all cell references in this row
            for cell in row_element:
                # Create a new cell
                cell_ref = cell.get('r', '')
                if cell_ref:
                    # Extract column letter and update row number
                    col_letter = ''.join([c for c in cell_ref if c.isalpha()])
                    new_cell = ET.Element(cell.tag, {'r': f"{col_letter}{current_row}"})
                else:
                    new_cell = ET.Element(cell.tag, cell.attrib)
                
                # Copy cell attributes
                for attr_name, attr_value in cell.attrib.items():
                    if attr_name != 'r':
                        new_cell.set(attr_name, attr_value)
                
                # Copy cell content
                for child in cell:
                    new_cell.append(child)
                
                new_row.append(new_cell)
            
            # Insert the row
            self._insert_row_in_order(sheet_data, new_row, current_row)
            current_row += 1
        
        print(f"Moved content inserted ({len(rows_data)} rows)")
    
    def _insert_row_in_order(self, sheet_data, new_row, row_num: int):
        """Insert row in the correct position to maintain order."""
        inserted = False
        for i, existing_row in enumerate(sheet_data):
            existing_row_num = int(existing_row.get('r', '0'))
            if existing_row_num > row_num:
                sheet_data.insert(i, new_row)
                inserted = True
                break
        
        if not inserted:
            sheet_data.append(new_row)

# Test the XML generator
if __name__ == "__main__":
    sample_products = [
        {
            "name": "Sodium Chloride pure, 97%",
            "cas_number": "7647-14-5",
            "packing": "500gm",
            "price": 50.00,
            "part": "SRL",
            "hs_code": "2501.00.00",
            "tax": 10.0
        },
        {
            "name": "Calcium Carbonate extrapure, 99%",
            "cas_number": "471-34-1",
            "packing": "500gm",
            "price": 75.00,
            "part": "Himedia",
            "hs_code": "2836.50.00",
            "tax": 5.0
        },
        {
            "name": "Magnesium Sulfate anhydrous",
            "cas_number": "7487-88-9",
            "packing": "100gm",
            "price": 60.00,
            "part": "SRL",
            "hs_code": "2833.21.00",
            "tax": 8.0
        }
    ]
    
    try:
        generator = XMLQuoteGenerator("/Users/saravanan/kavin/chatkit-kavin-scientific/mcp/quote.xlsx")
        output_path = generator.generate_quote(sample_products, "xml_generated_quote")
        
        # Verify images are preserved
        import zipfile
        with zipfile.ZipFile(output_path, 'r') as z:
            images = [f for f in z.namelist() if f.startswith('xl/media/')]
            print(f"\n✅ Images preserved: {len(images)}")
            for img in images:
                print(f"  - {img}")
        
        # Check file size
        import os
        file_size = os.path.getsize(output_path)
        print(f"File size: {file_size:,} bytes")
        
    except Exception as e:
        print(f"❌ Error: {e}")
