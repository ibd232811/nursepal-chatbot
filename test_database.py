import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv()

async def test_query():
    # Database connection
    db_password = os.getenv('DB_PASSWORD', '')
    print(f"Connecting to {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')} as {os.getenv('DB_USER')}")

    pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', '192.168.1.221'),
        port=int(os.getenv('DB_PORT', 5604)),
        user=os.getenv('DB_USER', 'nursepal'),
        password=db_password,
        database=os.getenv('DB_NAME', 'nursepal')
    )
    
    specialty = "ED"
    state = "NC"
    
    # Get detailed statistics
    query = """
        SELECT
            MIN("billRate") as min_rate,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "billRate") as p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY "billRate") as median,
            AVG("billRate") as average,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "billRate") as p75,
            MAX("billRate") as max_rate,
            COUNT(*) as count,
            STDDEV("billRate") as stddev
        FROM vmsrawscrape_prod
        WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
            AND LOWER(state) = LOWER($2)
            AND "billRate" IS NOT NULL
            AND "startDate" >= NOW() - INTERVAL '3 months'
    """
    
    async with pool.acquire() as conn:
        result = await conn.fetchrow(query, specialty, state)
        
        print(f"\n📊 ED in NC - Bill Rate Statistics:")
        print(f"   Sample Size: {result['count']}")
        print(f"   Minimum: ${result['min_rate']:.2f}/hr")
        print(f"   25th Percentile: ${result['p25']:.2f}/hr")
        print(f"   Median (50th): ${result['median']:.2f}/hr")
        print(f"   Average: ${result['average']:.2f}/hr")
        print(f"   75th Percentile: ${result['p75']:.2f}/hr")
        print(f"   Maximum: ${result['max_rate']:.2f}/hr")
        print(f"   Std Dev: ${result['stddev']:.2f}")
        
        # Get some sample records to see the data
        sample_query = """
            SELECT "billRate", specialty, city, state, "startDate"
            FROM vmsrawscrape_prod
            WHERE specialty ~ ('(^|\\s|-)' || $1 || '($|\\s)')
                AND LOWER(state) = LOWER($2)
                AND "billRate" IS NOT NULL
                AND "startDate" >= NOW() - INTERVAL '3 months'
            ORDER BY "billRate"
            LIMIT 10
        """
        
        samples = await conn.fetch(sample_query, specialty, state)
        print(f"\n📋 Sample Records (Lowest 10 rates):")
        for row in samples:
            print(f"   ${row['billRate']:.2f}/hr - {row['specialty']} in {row['city']}, {row['state']}")
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_query())
