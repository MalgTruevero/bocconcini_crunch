import pathlib, sys, time
import bocconcini as b

cl = b.LlamaCppClient()

luoghi = ["oasi","cava","stazione","ponte","torre","galleria","mercato","tempio"]
azioni = ["trovarono","persero","discussero","ripararono","abbandonarono","scoprirono"]
oggetti = ["una bussola","una lettera","una chiave","una lanterna","una corda","un registro"]

frasi = []
for i in range(120):
    frasi.append(f"Al {luoghi[i%8]} i viaggiatori {azioni[(i*3)%6]} {oggetti[(i*5)%6]}.")

# Aghi finti, per confonderlo
frasi[15] = "Il custode della torre si chiamava Aldo Verano e custodiva il numero 4718."
frasi[34] = "Il custode della torre si chiamava Aldo Verani e custodiva il numero 4718."
frasi[58] = "Il custode della torre si chiamava Aldo Verano e custodiva il numero 4719."
frasi[102] = "Il custode della torre si chiamava Paolo Verani e custodiva il numero 4719."
frasi[110] = "Il custode della torre si chiamava Aldo Verani e custodiva il numero 4710."

# Ago vero, nascosto in mezzo, posizione 87
frasi[87] = "Il custode della torre si chiamava Aldo Verani e custodiva il numero 4719."

storia = "\n".join(frasi)
print(f"storia: {len(storia)} caratteri, {b.estimate_tokens(storia,'text')} token stimati, {len(frasi)} frasi")

t0 = time.time()
r = cl.chat_full(
    "Leggi tutta la storia e rispondi in una riga, in italiano.\n\n" + storia +
    "\n\nDomanda: Come si chiamava ESATTAMENTE il custode della torre che custodiva il numero 4719? "
    "Attenzione: ci sono altri custodi con nomi e numeri quasi uguali. Rispondi solo con nome, cognome e numero.",
    max_tokens=60, continua=False
)
print(f"tempo: {time.time()-t0:.0f}s | cognitive_limit: {r.meta.get('cognitive_limit')}")
print("risposta:", r.text[:300])
print("ago VERO recuperato:", "Aldo Verani" in r.text and "4719" in r.text)
print("ha preso un ago FINTO?:", "Verano" in r.text or "Paolo" in r.text or "4718" in r.text or "4710" in r.text)
