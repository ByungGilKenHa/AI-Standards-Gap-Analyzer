"""Opt-in local Ollama educational explanation, never part of automatic reports."""
import json
from urllib.request import Request, urlopen


def study_clause(clause, previous, revised, model='qwen3:1.7b', timeout=180):
    if not (previous.strip() or revised.strip()):
        raise ValueError('No extracted text available for this clause.')
    # Keep input bounded for small local models; clearly mark truncation.
    max_chars = 3800
    prior, current = previous[:max_chars], revised[:max_chars]
    prompt = (f'You are an educational tutor, NOT a compliance auditor. Explain clause {clause} in simple English. '
              'Explain previous wording, revised wording, observed differences, one practical learning example, and two questions for further study. '
              'Separate directly observed text from possible interpretation. Never assert new obligations, equivalence, or compliance. '
              'If the supplied text is incomplete, say so. No external ISO knowledge is verified. '
              f'Previous extracted text (possibly truncated):\n{prior}\n\nRevised extracted text (possibly truncated):\n{current}')
    payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False, 'options': {'temperature': 0.1, 'num_predict': 650}}).encode()
    req = Request('http://127.0.0.1:11434/api/generate', data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=timeout) as response:
        result = json.load(response)
    answer = str(result.get('response', '')).strip()
    if not answer:
        raise ValueError('Local model returned an empty response.')
    return answer
