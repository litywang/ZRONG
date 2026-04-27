import sys
sys.path.insert(0, '.')
from utils import mainland_friendly_score, is_asia, is_china_mainland, ASIA_REGIONS

print('ASIA_REGIONS:', ASIA_REGIONS)

nodes = [
    {'server': '223.5.5.5', 'sni': '', 'name': 'CN-direct'},
    {'server': '104.16.249.249', 'sni': 'jp.example.com', 'name': 'JP-SNI'},
    {'server': '8.8.8.8', 'sni': '', 'name': 'US-Google'},
    {'server': '1.1.1.1', 'sni': 'sg.cloudflare.com', 'name': 'SG-CF'},
]

for n in nodes:
    score = mainland_friendly_score(n)
    print(f"{n['name']:15} score={score}")
