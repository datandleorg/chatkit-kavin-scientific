#!/usr/bin/env python3
"""
Test script for the MCP Quote Generator Server
"""

import asyncio
import json
from xml_quote_generator import XMLQuoteGenerator

async def test_quote_generation():
    """Test the quote generation functionality."""
    
    sample_products = [
    {
        "name": "Spatula SS Spoon & Flat 6 inch",
        "part": "4519",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 24,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula SS Spoon & Flat 8 inch",
        "part": "4520",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 30,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula SS Spoon & Flat 10 inch",
        "part": "4515",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 65,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula SS Spoon & Flat 12 inch",
        "part": "4516",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 71,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula Polypropylene 6 inch",
        "part": "5655",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 12,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },
     {
        "name": "Spatula Polypropylene 6 inch",
        "part": "5655",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 12,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },
     {
        "name": "Spatula Polypropylene 6 inch",
        "part": "5655",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 12,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula Polypropylene 8 inch",
        "part": "5656",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 14,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Spatula Nickel-Plated 6 inch",
        "part": "4531",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 46,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Ointment Spatula 6 inch (SS blade, wooden handle)",
        "part": "4534",
        "cas_number": "N/A",
        "packing": "Each",
        "price": 72,
        "hs_code": "8205.59",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Plastic Spatula (Polylab) 150mm - Pack of 12",
        "part": "81301",
        "cas_number": "N/A",
        "packing": "Pack of 12",
        "price": 90,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },
    {
        "name": "Plastic Spatula (Polylab) 200mm - Pack of 12",
        "part": "81302",
        "cas_number": "N/A",
        "packing": "Pack of 12",
        "price": 114,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },   {
        "name": "Plastic Spatula (Polylab) 200mm - Pack of 12",
        "part": "81302",
        "cas_number": "N/A",
        "packing": "Pack of 12",
        "price": 114,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },   {
        "name": "Plastic Spatula (Polylab) 200mm - Pack of 12",
        "part": "81302",
        "cas_number": "N/A",
        "packing": "Pack of 12",
        "price": 114,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    },   {
        "name": "Plastic Spatula (Polylab) 200mm - Pack of 12",
        "part": "81302",
        "cas_number": "N/A",
        "packing": "Pack of 12",
        "price": 114,
        "hs_code": "3926.90",
        "tax": 18,
        "quantity": 1
    }
]
    # Sample product data (following the reference structure)
    sample_products11 = [
        {
            "name": "Sodium Chloride pure, 97%",
            "cas_number": "7647-14-5",  # Used as catno
            "packing": "500gm",  # Used as unit
            "price": 50.00,  # Used as rate
            "part": "SRL",  # Used as brand
            "hs_code": "2501.00.00",  # Used as hsn
            "tax": 10.0  # Used as discount percentage
        },
        {
            "name": "Calcium Carbonate extrapure, 99%",
            "cas_number": "471-34-1",  # Used as catno
            "packing": "500gm",  # Used as unit
            "price": 75.00,  # Used as rate
            "part": "Himedia",  # Used as brand
            "hs_code": "2836.50.00",  # Used as hsn
            "tax": 5.0  # Used as discount percentage
        },
        {
            "name": "Magnesium Sulfate anhydrous",
            "cas_number": "7487-88-9",  # Used as catno
            "packing": "100gm",  # Used as unit
            "price": 60.00,  # Used as rate
            "part": "SRL",  # Used as brand
            "hs_code": "2833.21.00",  # Used as hsn
            "tax": 8.0  # Used as discount percentage
        }
    ]
    
    try:
        # Test the generator
        generator = XMLQuoteGenerator("/Users/saravanan/kavin/chatkit-kavin-scientific/mcp/quote.xlsx")
        output_path = generator.generate_quote(sample_products, "test_quote")
        
        print(f"✅ Test successful! Quote generated at: {output_path}")
        print(f"Products processed: {len(sample_products)}")
        
        # Calculate total for verification
        total = sum(float(p['price']) * (1 + float(p['tax']) / 100) for p in sample_products)
        print(f"Total amount: ${total:.2f}")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_quote_generation())
