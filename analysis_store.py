"""Atomic, local, per-PDF/model persistent cache. No source PDF content is saved."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

CACHE_VERSION = '2.0.0'

def _root():
    root = Path(os.environ.get('GAP_ANALYZER_CACHE_DIR', Path.home() / '.ai_standards_gap_analyzer' / 'analysis_cache'))
    root.mkdir(parents=True, exist_ok=True)
    return root

def cache_path(old_hash, new_hash, model):
    key = hashlib.sha256(json.dumps([CACHE_VERSION, old_hash, new_hash, model], separators=(',', ':')).encode()).hexdigest()
    return _root() / (key + '.json')

def load(old_hash, new_hash, model):
    path=cache_path(old_hash,new_hash,model)
    try:
        with path.open(encoding='utf-8') as f: data=json.load(f)
        if data.get('version')==CACHE_VERSION and isinstance(data.get('analyses'),dict):
            return data['analyses'], data.get('failures',{})
    except (OSError,ValueError,TypeError):
        pass
    return {},{}

def save(old_hash,new_hash,model,analyses,failures):
    path=cache_path(old_hash,new_hash,model)
    payload={'version':CACHE_VERSION,'analyses':analyses,'failures':failures}
    fd,tmp=tempfile.mkstemp(prefix='.analysis_',suffix='.tmp',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(payload,f,ensure_ascii=False,indent=2)
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
