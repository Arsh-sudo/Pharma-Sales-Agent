"""
Demo Companies - Fallback data when scraping returns no results
These are real pharmaceutical companies for testing the pipeline.
"""

SAMPLE_PHARMA_COMPANIES = [
    {
        "name": "Sun Pharmaceutical Industries",
        "website": "https://www.sunpharma.com",
        "source": "demo"
    },
    {
        "name": "Dr. Reddy's Laboratories",
        "website": "https://www.drreddys.com",
        "source": "demo"
    },
    {
        "name": "Cipla Limited",
        "website": "https://www.cipla.com",
        "source": "demo"
    },
    {
        "name": "Lupin Limited",
        "website": "https://www.lupin.com",
        "source": "demo"
    },
    {
        "name": "Aurobindo Pharma",
        "website": "https://www.aurobindo.com",
        "source": "demo"
    },
    {
        "name": "Zydus Lifesciences",
        "website": "https://www.zyduslife.com",
        "source": "demo"
    },
    {
        "name": "Torrent Pharmaceuticals",
        "website": "https://www.torrentpharma.com",
        "source": "demo"
    },
    {
        "name": "Glenmark Pharmaceuticals",
        "website": "https://www.glenmarkpharma.com",
        "source": "demo"
    },
    {
        "name": "Biocon Limited",
        "website": "https://www.biocon.com",
        "source": "demo"
    },
    {
        "name": "Alembic Pharmaceuticals",
        "website": "https://www.alembicpharmaceuticals.com",
        "source": "demo"
    }
]

def get_demo_companies(count=5):
    """Return sample pharma companies for testing."""
    import random
    selected = random.sample(SAMPLE_PHARMA_COMPANIES, min(count, len(SAMPLE_PHARMA_COMPANIES)))
    return selected
