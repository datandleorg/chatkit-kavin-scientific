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
        self.supported_formats = ['.pdf', '.docx', '.txt', '.html', '.md']
    
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
        """Process PDF using Docling-parse (exactly like working extractor)"""
        try:
            # Use the exact same approach as the working extractor
            parser = pdf_parser_v2(str(file_path))
            parser.load_document('doc1', str(file_path))
            result = parser.parse_pdf_from_key('doc1')
            
            # Extract text from all pages - EXACTLY like working extractor
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
                    
                    # Extract text from cells - EXACTLY like working extractor
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
                    
                    # Extract text from lines (lines appear to be geometric shapes, not text)
                    # Lines in this structure seem to be drawing elements, not text lines
                    # We'll skip lines for now since they don't contain text - EXACTLY like working extractor
                    
                    text_data["text_elements"].extend(page_elements)
                    text_data["full_text"] += page_text
                    
                    text_data["pages"][str(page_idx)] = {
                        "text": page_text,
                        "char_count": len(page_text),
                        "word_count": len(page_text.split()),
                        "elements": page_elements
                    }
            
            # Use the full_text from the working extractor approach
            content = text_data["full_text"]
            
            metadata = {
                "file_type": "pdf",
                "pages_count": text_data["total_pages"],
                "total_elements": len(text_data["text_elements"]),
                "document_info": result.get('info', {}),
                "extraction_method": "docling-parse"
            }
            
            if not content.strip():
                logger.warning(f"No text content extracted from PDF: {file_path.name}")
                content = f"PDF document {file_path.name} - No readable text content found"
            
            logger.info(f"Extracted {len(text_data['text_elements'])} text elements from {text_data['total_pages']} pages")
            return content, metadata
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path.name}: {e}")
            raise Exception(f"Failed to process PDF: {str(e)}")
    
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