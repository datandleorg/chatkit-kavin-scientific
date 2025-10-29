import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
import logging
from docling_parse.pdf_parser import pdf_parser_v2
import json

from models.schemas import DocumentData, DocumentChunk

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Service for processing documents using Docling"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.docx', '.txt', '.html', '.md', '.xlsx', '.xls', '.csv']
    
    async def process_document(
        self, 
        file_path: Path, 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200
    ) -> Dict[str, Any]:
        """
        Process a document and extract text chunks using Docling
        
        Args:
            file_path: Path to the document file
            chunk_size: Maximum size of each text chunk
            chunk_overlap: Overlap between consecutive chunks
            
        Returns:
            Dictionary containing processed document data
        """
        start_time = time.time()
        file_extension = file_path.suffix.lower()
        
        if file_extension not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        logger.info(f"Processing document: {file_path.name}")
        
        try:
            # Extract text based on file type
            if file_extension == '.pdf':
                content, metadata = await self._process_pdf(file_path)
            elif file_extension == '.docx':
                content, metadata = await self._process_docx(file_path)
            elif file_extension == '.txt':
                content, metadata = await self._process_txt(file_path)
            elif file_extension in ['.xlsx', '.xls']:
                content, metadata = await self._process_excel(file_path)
            elif file_extension == '.csv':
                content, metadata = await self._process_csv(file_path)
            else:
                # For other formats, try basic text extraction
                content, metadata = await self._process_generic(file_path)
            
            # Create chunks with metadata
            chunks = self._create_chunks(content, chunk_size, chunk_overlap, metadata)
            
            processing_time = time.time() - start_time
            
            return {
                "filename": file_path.name,
                "content": content,
                "chunks": chunks,
                "metadata": metadata,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Error processing document {file_path.name}: {e}")
            raise Exception(f"Failed to process document: {str(e)}")
    
    async def _process_pdf(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process PDF using Docling-parse with pypdf fallback"""
        # Try Docling first
        docling_success = False
        try:
            # Use the exact same approach as the working extractor
            parser = pdf_parser_v2(str(file_path))
            parser.load_document('doc1', str(file_path))
            result = parser.parse_pdf_from_key('doc1')
            
            # Extract text from all pages
            text_data = {
                "total_pages": len(result['pages']),
                "text_elements": [],
                "full_text": "",
                "pages": {}
            }
            
            pages_to_process = range(len(result['pages']))
            
            for page_idx in pages_to_process:
                if 0 <= page_idx < len(result['pages']):
                    page = result['pages'][page_idx]
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
                    
                    text_data["text_elements"].extend(page_elements)
                    text_data["full_text"] += page_text
                    
                    text_data["pages"][str(page_idx)] = {
                        "text": page_text,
                        "char_count": len(page_text),
                        "word_count": len(page_text.split()),
                        "elements": page_elements
                    }
            
            content = text_data["full_text"]
            
            metadata = {
                "file_type": "pdf",
                "pages_count": text_data["total_pages"],
                "total_elements": len(text_data["text_elements"]),
                "document_info": result.get('info', {}),
                "extraction_method": "docling-parse"
            }
            
            # Check if we actually got meaningful content
            if content.strip():
                docling_success = True
                logger.info(f"Extracted {len(text_data['text_elements'])} text elements from {text_data['total_pages']} pages using Docling")
            else:
                logger.warning(f"No text content extracted from PDF with Docling: {file_path.name}, falling back to pypdf")
            
        except Exception as docling_error:
            logger.warning(f"Docling processing failed for {file_path.name}: {docling_error}")
        
        # If Docling failed or extracted no content, try pypdf
        if not docling_success:
            try:
                logger.info("Falling back to pypdf extraction...")
                return await self._process_pdf_with_pypdf(file_path)
            except Exception as pypdf_error:
                logger.error(f"Both Docling and pypdf failed for PDF {file_path.name}: {pypdf_error}")
                raise Exception(f"Failed to process PDF with both Docling and pypdf: {str(pypdf_error)}")
        
        # Return Docling results if successful
        return content, metadata
    
    async def _process_pdf_with_pypdf(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process PDF using pypdf as fallback when Docling fails"""
        try:
            from pypdf import PdfReader
            
            reader = PdfReader(str(file_path))
            
            text_content = []
            total_elements = 0
            
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_content.append(f"=== Page {page_num} ===\n{page_text}")
                        total_elements += len(page_text.split())
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
                    continue
            
            content = "\n\n".join(text_content)
            
            if not content.strip():
                logger.warning(f"No text content extracted from PDF with pypdf: {file_path.name}")
                content = f"PDF document {file_path.name} - No readable text content found"
            
            metadata = {
                "file_type": "pdf",
                "pages_count": len(reader.pages),
                "total_elements": total_elements,
                "document_info": reader.metadata if reader.metadata else {},
                "extraction_method": "pypdf"
            }
            
            logger.info(f"Extracted text from {len(reader.pages)} pages using pypdf")
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF with pypdf {file_path.name}: {e}")
            raise Exception(f"Failed to process PDF with pypdf: {str(e)}")
    
    async def _process_docx(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process DOCX file"""
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            content_parts = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    content_parts.append(paragraph.text.strip())
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        content_parts.append(" | ".join(row_text))
            
            content = "\n".join(content_parts)
            
            metadata = {
                "file_type": "docx",
                "paragraphs_count": len(doc.paragraphs),
                "tables_count": len(doc.tables),
                "extraction_method": "python-docx"
            }
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing DOCX {file_path.name}: {e}")
            raise Exception(f"Failed to process DOCX: {str(e)}")
    
    async def _process_excel(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process Excel file (XLSX/XLS)"""
        try:
            from openpyxl import load_workbook
            from openpyxl.cell.cell import MergedCell
            
            workbook = load_workbook(filename=file_path, data_only=True)
            content_parts = []
            
            total_sheets = len(workbook.sheetnames)
            total_rows = 0
            total_cells = 0
            sheets_data = []
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_content = []
                sheet_rows = 0
                sheet_cells = 0
                
                # Add sheet header
                sheet_content.append(f"\n=== Sheet: {sheet_name} ===")
                
                # Get merged cells for reference and track which cells are merged (but not the top-left)
                merged_cell_coords = set()
                for merged_range in sheet.merged_cells.ranges:
                    # Get all cells in the merged range
                    for row in range(merged_range.min_row, merged_range.max_row + 1):
                        for col in range(merged_range.min_col, merged_range.max_col + 1):
                            cell_coord = sheet.cell(row, col).coordinate
                            # Don't skip the top-left cell
                            if cell_coord != sheet.cell(merged_range.min_row, merged_range.min_col).coordinate:
                                merged_cell_coords.add(cell_coord)
                
                # Process rows with data
                for row_idx, row in enumerate(sheet.iter_rows(min_row=1, values_only=False), 1):
                    row_data = []
                    row_empty = True
                    
                    for col_idx, cell in enumerate(row, 1):
                        # Skip if cell is part of a merged range (but not the top-left)
                        if isinstance(cell, MergedCell):
                            continue
                        
                        if cell.coordinate in merged_cell_coords:
                            continue
                        
                        # Get cell value
                        cell_value = None
                        if cell.data_type == 'f':  # Formula
                            # Try to get calculated value first
                            if cell.value is not None:
                                cell_value = str(cell.value)
                            # Also store the formula itself
                            formula_text = f"(Formula: {cell.formula})"
                            cell_value = cell_value if cell_value else formula_text
                        else:
                            cell_value = cell.value
                        
                        if cell_value is not None:
                            cell_str = str(cell_value).strip()
                            if cell_str:
                                row_data.append(cell_str)
                                row_empty = False
                    
                    if not row_empty:
                        # Join row data with tab separator for table structure
                        sheet_content.append("\t".join(row_data))
                        row_cell_count = len(row_data)
                        sheet_rows += 1
                        sheet_cells += row_cell_count
                        total_rows += 1
                        total_cells += row_cell_count
                
                sheets_data.append({
                    "name": sheet_name,
                    "rows": sheet_rows,
                    "cells": sheet_cells
                })
                
                content_parts.extend(sheet_content)
            
            content = "\n".join(content_parts)
            
            metadata = {
                "file_type": "excel",
                "workbook_format": "xlsx" if file_path.suffix == '.xlsx' else "xls",
                "total_sheets": total_sheets,
                "sheet_names": workbook.sheetnames,
                "total_rows": total_rows,
                "total_cells": total_cells,
                "sheets_data": sheets_data,
                "extraction_method": "openpyxl"
            }
            
            workbook.close()
            
            logger.info(f"Extracted {total_rows} rows from {total_sheets} sheets")
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing Excel {file_path.name}: {e}")
            raise Exception(f"Failed to process Excel file: {str(e)}")
    
    async def _process_csv(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process CSV file"""
        try:
            import pandas as pd
            
            # Read CSV with automatic encoding detection
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    df = pd.read_csv(file_path, encoding='latin-1')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='cp1252', errors='ignore')
            
            content_parts = []
            
            # Get number of rows and columns
            total_rows = len(df)
            total_cols = len(df.columns)
            
            # Add header row
            headers = df.columns.tolist()
            content_parts.append("\t".join([str(h) for h in headers]))
            
            # Add data rows
            for index, row in df.iterrows():
                row_data = []
                for col in df.columns:
                    cell_value = row[col]
                    # Handle NaN values
                    if pd.isna(cell_value):
                        cell_value = ""
                    else:
                        cell_value = str(cell_value).strip()
                    row_data.append(cell_value)
                
                # Only add non-empty rows
                if any(cell for cell in row_data if cell):
                    content_parts.append("\t".join(row_data))
            
            content = "\n".join(content_parts)
            
            # Count non-empty cells
            non_empty_cells = df.notna().sum().sum()
            
            metadata = {
                "file_type": "csv",
                "total_rows": total_rows,
                "total_columns": total_cols,
                "column_names": headers,
                "non_empty_cells": int(non_empty_cells),
                "extraction_method": "pandas"
            }
            
            logger.info(f"Extracted {total_rows} rows and {total_cols} columns from CSV")
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing CSV {file_path.name}: {e}")
            raise Exception(f"Failed to process CSV file: {str(e)}")
    
    async def _process_txt(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metadata = {
                "file_type": "txt",
                "char_count": len(content),
                "line_count": len(content.splitlines()),
                "extraction_method": "direct_read"
            }
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing TXT {file_path.name}: {e}")
            raise Exception(f"Failed to process TXT: {str(e)}")
    
    async def _process_generic(self, file_path: Path) -> tuple[str, Dict[str, Any]]:
        """Process other file types with basic text extraction"""
        try:
            # Try to read as text file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            metadata = {
                "file_type": file_path.suffix.lower(),
                "char_count": len(content),
                "extraction_method": "generic_text_read"
            }
            
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing generic file {file_path.name}: {e}")
            raise Exception(f"Failed to process file: {str(e)}")
    
    def _create_chunks(self, text: str, chunk_size: int, chunk_overlap: int, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks with page information"""
        if not text.strip():
            return []

        chunks = []
        start = 0
        chunk_index = 0
        
        # Estimate page numbers based on text length (rough approximation)
        total_chars = len(text)
        estimated_pages = max(1, total_chars // 2000)  # Assume ~2000 chars per page
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings within the last 100 characters
                search_start = max(start, end - 100)
                sentence_end = text.rfind('.', search_start, end)
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    # Look for word boundary
                    word_end = text.rfind(' ', search_start, end)
                    if word_end > start:
                        end = word_end
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                # Estimate page number for this chunk
                estimated_page = min(estimated_pages, max(1, (start / total_chars) * estimated_pages + 1))
                
                chunks.append({
                    "text": chunk_text,
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                    "metadata": {
                        "chunk_size": len(chunk_text),
                        "char_start": start,
                        "char_end": end,
                        "page_number": int(estimated_page),
                        **(metadata or {})
                    }
                })
                chunk_index += 1
            
            # Move start position with overlap
            start = end - chunk_overlap
            if start >= len(text):
                break
        
        logger.info(f"Created {len(chunks)} chunks from document")
        return chunks