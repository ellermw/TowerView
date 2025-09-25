#!/usr/bin/env python3
"""
Worker entry point for running Celery worker or beat scheduler
"""

import sys
import logging
from worker.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'beat':
        # Run as scheduler
        celery_app.start(['celery', 'beat', '-l', 'info'])
    else:
        # Run as worker
        celery_app.start(['celery', 'worker', '-l', 'info'])