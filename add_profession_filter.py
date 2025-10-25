#!/usr/bin/env python3
"""
Script to add profession filter to all database queries
"""

import re

def add_profession_filter_to_file():
    with open('database_service.py', 'r') as f:
        content = f.read()

    # For methods that use parameters object, add profession extraction
    methods_needing_profession = [
        'get_clients_by_rate',
        'get_comparable_jobs',
        'get_highest_rates_in_market',
        'get_lead_opportunities'
    ]

    for method in methods_needing_profession:
        # Find the method and add profession extraction after other getattr lines
        pattern = f'(async def {method}.*?\\n.*?try:.*?\\n.*?specialty = getattr.*?\\n.*?location = getattr.*?\\n)'
        replacement = r'\1            profession = getattr(parameters, \'profession\', None)\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        # Add profession_filter generation after rate_column definition
        pattern = f'(async def {method}.*?rate_label.*?\\n)'
        replacement = r'\1\n            # Get profession filter\n            profession_filter = self._get_profession_filter(profession)\n'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE)

    # Add profession_filter to all WHERE clauses in FROM vmsrawscrape_prod queries
    # Pattern: Find "startDate" >= lines and add profession_filter after them
    pattern = r'(AND "startDate" >= [^\n]+\n)'
    replacement = r'\1                        {profession_filter}\n'
    content = re.sub(pattern, replacement, content)

    with open('database_service.py', 'w') as f:
        f.write(content)

    print("✅ Added profession filters to database queries")

if __name__ == '__main__':
    add_profession_filter_to_file()
