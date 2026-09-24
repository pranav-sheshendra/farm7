"""Check catalog completeness and script integrity (not translation accuracy)."""
import json
import sys
import unicodedata
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from languages import LANGUAGE_MAP

scripts = {
    'as':'BENGALI', 'bn':'BENGALI', 'brx':'DEVANAGARI', 'doi':'DEVANAGARI',
    'gu':'GUJARATI', 'hi':'DEVANAGARI', 'kn':'KANNADA', 'ks':'ARABIC',
    'gom':'DEVANAGARI', 'mai':'DEVANAGARI', 'ml':'MALAYALAM', 'mni-Mtei':'MEETEI',
    'mr':'DEVANAGARI', 'ne':'DEVANAGARI', 'or':'ORIYA', 'pa':'GURMUKHI',
    'sa':'DEVANAGARI', 'sat':'OL CHIKI', 'sd':'ARABIC', 'ta':'TAMIL',
    'te':'TELUGU', 'ur':'ARABIC', 'en':'LATIN',
}
source=json.loads((root/'static/locales/en.json').read_text(encoding='utf-8'))
report={}
for code in LANGUAGE_MAP:
    path=root/'static/locales'/f'{code}.json'
    if not path.exists():
        report[code]={'available':False}
        continue
    catalog=json.loads(path.read_text(encoding='utf-8'))
    assert set(catalog)==set(source),code
    assert all(isinstance(v,str) and v.strip() and '\ufffd' not in v for v in catalog.values()),code
    letters=[c for value in catalog.values() for c in value if c.isalpha()]
    fraction=sum(scripts[code] in unicodedata.name(c,'') for c in letters)/len(letters)
    assert fraction>0.65,(code, fraction, 'Unexpected script; review this catalog')
    report[code]={'available':True,'keys':len(catalog),'expected_script_fraction':round(fraction,3),'native_review':code=='en'}
(root/'artifacts/locale-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
missing=[code for code,data in report.items() if not data['available']]
print('Validated catalogs:',len(report)-len(missing),'Missing:',','.join(missing) or 'none')
if '--all' in sys.argv:
    assert not missing,missing
