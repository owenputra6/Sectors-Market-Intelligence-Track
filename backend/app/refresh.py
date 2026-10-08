"""python -m app.refresh --check: local status only; no flag: refresh if due."""
import argparse
import json
import logging
import os
from .config import settings
from .sectors_client import SectorsClient
from .weekly import WeeklyStore

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    store = WeeklyStore(SectorsClient(settings))
    store.log_status()
    if args.check:
        print(json.dumps(store.status(), indent=2))
    elif os.getenv('WEEKLY_REFRESH_ENABLED', 'true').strip().lower() not in {'1', 'true', 'yes', 'on'}:
        logging.info('WEEKLY_REFRESH_ENABLED=false; refresh command exited without provider calls.')
    else:
        store.refresh()

if __name__ == '__main__':
    main()
