import re
p = 'new_tail.txt'
s = open(p, encoding='utf-8').read()
m = {'genitori': 'parents', 'visti': 'seen', 'vis': 'shown',
     'usati': 'used', 'blocco': 'block', 'parti': 'parts', 'et': 'span_label'}
for a, b in m.items():
    s = re.sub(r'\b%s\b' % a, b, s)
open(p, 'w', encoding='utf-8').write(s)
print('ok')
