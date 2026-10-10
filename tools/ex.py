import re
t = open('.historia/2/3.patch').read()
m = re.search(r'diff --git a/survival.py b/survival.py\nnew file.*?\n\+\+\+ b/survival.py\n@@[^\n]*\n(.*?)\ndiff --git', t, re.S)
open('survival.py', 'w').write(''.join(l[1:] + '\n' for l in m.group(1).split('\n')))
