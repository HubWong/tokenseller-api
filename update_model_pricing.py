#!/usr/bin/env python
"""Script to update model_pricing currency to 'usd'"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal


async def update_model_pricing_currency():
    """Update all model_pricing records to set currency = 'usd'"""
    try:
        async with AsyncSessionLocal() as session:
            # Execute the update query
            result = await session.execute(
                text("UPDATE model_pricing SET currency = 'usd'")
            )
            await session.commit()
            
            print(f"✓ Successfully updated {result.rowcount} record(s)")
            print("✓ model_pricing currency field has been set to 'usd'")
            
            # Verify the update
            verify_result = await session.execute(
                text("SELECT id, model_name, currency FROM model_pricing LIMIT 5")
            )
            records = verify_result.fetchall()
            
            if records:
                print("\nVerification - Sample records:")
                for record in records:
                    print(f"  ID: {record[0]}, Model: {record[1]}, Currency: {record[2]}")
            
    except Exception as e:
        print(f"✗ Error updating model_pricing: {str(e)}")
        raise


if __name__ == "__main__":
    print("Starting model_pricing currency update...\n")
    asyncio.run(update_model_pricing_currency())
    print("\n✓ Update completed!")
