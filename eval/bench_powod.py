"""Benchmark JEV dla czynnosc_powod_id (60 przykładów): warianty pytań/opcji/kontekstu."""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import jev
from app.pdf_text import pdf_to_text

PL = ["Decyzja o odrzuceniu oferty","Ogłoszenie wyboru oferty","Decyzja o wykluczeniu wykonawcy","Publikacja specyfikacji warunków zamówienia (SWZ)","Modyfikacja treści SWZ","Odpowiedzi i wyjaśnienia do SWZ","Zaniechanie odrzucenia oferty","Zaniechanie wykluczenia wykonawcy","Decyzja o unieważnieniu postępowania","Zaniechanie unieważnienia postępowania","Opis przedmiotu zamówienia (OPZ)","Inna czynność"]
EN = ["Rejection of an offer","Announcement of the selected (best) offer","Exclusion of a contractor","Publication of the tender specification (SWZ)","Modification of the SWZ content","Answers and clarifications to the SWZ","Failure to reject an offer","Failure to exclude a contractor","Cancellation of the procedure","Failure to cancel the procedure","Description of the subject of the contract (OPZ)","Other action"]
QPL = "Którą czynność (lub zaniechanie) zamawiającego zaskarża PIERWSZY zarzut odwołania (Zarzut nr 1)?"
QEN = "This is a Polish public procurement appeal. Which action or omission of the contracting authority does the FIRST objection (Zarzut nr 1) challenge?"

def ctx_focus(t):
    a = re.search(r'Zamawiając\w+\s+w\s+dniu', t); z = re.search(r'Zarzut\w*\s+nr\s*1', t, re.I); z2 = re.search(r'Zarzut\w*\s+nr\s*2', t, re.I)
    parts = []
    if a: parts.append(t[a.start():a.start()+700])
    if z: parts.append(t[z.start():(z2.start() if z2 and z2.start() > z.start() else z.start()+1500)][:1500])
    return re.sub(r'[ \t]+', ' ', '\n'.join(parts) or t[:2500])

def ctx_head(t):
    return re.sub(r'[ \t]+', ' ', t[:3500])

d = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'tasks/uzp/dane')
data = []
for c in sorted(d.iterdir()):
    t = pdf_to_text(c/'odwolanie.pdf')[0]
    g = json.loads((c/'odwolanie.json').read_text(encoding='utf-8'))['OdwolanieKIO']['czynnosc_powod_id']
    data.append((c.name, t, g))
for name, opts, q, ctx in [('PL-focus', PL, QPL, ctx_focus), ('EN-focus', EN, QEN, ctx_focus), ('PL-head', PL, QPL, ctx_head)]:
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda x: jev.choice(ctx(x[1]), q, opts), data))
    ok = 0; errs = []
    for (n, _, g), (i, p, _) in zip(data, res):
        ok += i + 1 == g
        if i + 1 != g: errs.append(f"{n[-2:]}:{g}->{i+1}({p:.2f})")
    print(f"{name:9} acc={ok}/60  czas={time.time()-t0:.1f}s  błędy: {' '.join(errs)}")
