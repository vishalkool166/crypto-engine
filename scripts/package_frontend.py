"""Copy freshly built assets to a staging web root. Never touches production itself."""
from pathlib import Path
import argparse
import shutil

root = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--destination',type=Path,required=True)
args=parser.parse_args()
source=root/'dashboard'/'dist'
if not source.is_dir() or not (source/'index.html').is_file():
    raise SystemExit('Build React first: (cd dashboard && npm ci && npm run build)')
target=args.destination.resolve()
if target.exists() and any(target.iterdir()):
    raise SystemExit('Destination must be empty; refuse to erase an existing deployment')
if target == (root/'frontend').resolve():
    raise SystemExit('Do not overwrite the backend source snapshot without a staging release and rollback plan')
shutil.copytree(source,target,dirs_exist_ok=True)
print(f'Copied fresh build to {target}')
