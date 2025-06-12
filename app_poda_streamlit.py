
import streamlit as st
import pandas as pd, fitz, re, os, io, zipfile, tempfile

# -------------- Utils --------------
def clean(txt: str) -> str:
    return re.sub(r"\s+", " ", txt.replace("\n", " ")).strip()

def find(pattern: str, txt: str, last=False):
    matches = list(re.finditer(pattern, txt, re.I))
    if not matches:
        return None
    return matches[-1 if last else 0].group(1).strip()

# -------------- Analysis for project PDFs --------------
def analisa_fotos(path: str, tol_x=100, tol_y=400):
    doc = fitz.open(path)
    full = clean(" ".join(p.get_text() for p in doc))

    proj_text = find(r"Projeto\s*[:\-]?\s*([A-Z0-9./_-]+)", full)
    proj_fname = os.path.splitext(os.path.basename(path))[0].split("_")[0]
    proj = proj_text if proj_text else proj_fname

    circ = find(r"Circuito\s*[:\-]?\s*([\w/\-]+)", full) or "(não informado)"
    equip = find(r"Equipamento\s*[:\-]?\s*([\w/\-]+)", full) or "(não informado)"
    nota = find(r"Nota\s*[:\-]?\s*([\w/\-]+)", full) or "(não informada)"
    pref = find(r"Prefeitura\s*[:\-]?\s*([\w À-ÖØ-öø-ÿ-]+?)(?:\s{2,}|Subprefeitura|Foto|Quantidade|Código|Cod|$)", full) or "(não informada)"
    subp = find(r"Subprefeitura\s*[:\-]?\s*([\w À-ÖØ-öø-ÿ-]+?)(?:\s{2,}|Foto|Quantidade|Código|Cod|$)", full) or "(não informada)"

    qtd, falt = [], {}
    for pg in doc:
        pg_txt = pg.get_text()
        qtd += [int(q) for q in re.findall(r"Quantidade\s*:?\s*(\d+)", pg_txt, re.I)]
        blocks = pg.get_text("dict")["blocks"]

        codes, seen = [], set()
        for b in blocks:
            if "lines" in b:
                for ln in b["lines"]:
                    for sp in ln["spans"]:
                        tx = sp["text"].strip()
                        if tx.isdigit() and sp["bbox"][0] < 50 and tx not in seen:
                            seen.add(tx); codes.append(tx)

        labels = [
            {"tipo": sp["text"].strip().lower(), "x": sp["bbox"][0], "y": sp["bbox"][1]}
            for b in blocks if "lines" in b
            for ln in b["lines"]
            for sp in ln["spans"]
            if re.search(r"foto inspeção|foto execução|foto antes da recolha|foto depois da recolha", sp["text"].strip().lower())
        ]
        imgs = [{"x": b["bbox"][0], "y": b["bbox"][1]} for b in blocks if "image" in b]

        for idx, lb in enumerate(labels):
            tipo = lb["tipo"].replace("foto ", "").capitalize()
            cod = codes[idx // 4] if idx // 4 < len(codes) else ""
            pres = any(
                img["y"] > lb["y"]
                and abs(img["x"] - lb["x"]) <= tol_x
                and 0 < img["y"] - lb["y"] <= tol_y
                for img in imgs
            )
            if not pres:
                falt.setdefault(cod, set()).add(tipo)

    total_podas = sum(qtd)

    header = f"Projeto: {proj} Circuito: {circ} Equipamento: {equip} Nota: {nota}  Prefeitura: {pref}  Subprefeitura: {subp}"

    if falt:
        corpo = f"📍 Projeto: {proj} — fotos ausentes (total podas {total_podas})"
        nums = sorted((int(c) for c in falt if c.isdigit()), reverse=True)
        others = sorted((c for c in falt if not c.isdigit()), reverse=True)
        linhas = [f"codigo {c or '(código não informado)'} : {', '.join(sorted(falt[c]))}" for c in [*map(str, nums), *others]]
        status = "ausentes"
    else:
        corpo = f"📍 Projeto: {proj} — todas as fotos estão presentes (total podas {total_podas})"
        linhas = []
        status = "presentes"

    row = {
        "Projeto": proj,
        "Circuito": circ,
        "Equipamento": equip,
        "Nota": nota,
        "Prefeitura": pref,
        "Subprefeitura": subp,
        "Total_Podas": total_podas,
    }
    if status == "ausentes":
        row["Faltantes"] = "; ".join(linhas)

    return header, corpo, linhas, status, row

# -------------- Execução --------------
def analisa_execucao(path: str):
    doc = fitz.open(path)
    full = clean(" ".join(p.get_text() for p in doc))
    total = find(r"TOTAL GERAL\s*(\d+)", full, last=True) or ""
    mes = find(r"TOTAL GERAL\s*\d+\s+([A-Za-zÇ-ú]+)", full, last=True) or ""
    mun = find(r"MUNIC[IÍ]PIO\s*[:\-]?\s*([\w À-ÖØ-öø-ÿ]+)", full, last=True) or ""
    sub = find(r"SUBPREFEITURA\s*[:\-]?\s*([\w À-ÖØ-öø-ÿ]+)", full, last=True) or ""
    header = "Comunicação de Execução"
    corpo = f"TOTAL GERAL {total}  {mes}"
    linhas = [f"MUNICÍPIO: {mun}", f"SUBPREFEITURA: {sub}"]
    row = {"TOTAL_GERAL": total, "Mês": mes, "MUNICÍPIO": mun, "SUBPREFEITURA": sub}
    return header, corpo, linhas, row

# -------------- Display --------------
def mostrar(header: str, corpo: str, linhas, key):
    st.markdown(f"**{header}**")
    st.text_area("Resultado", "\n".join([corpo, *linhas]) if linhas else corpo, height=300, key=key)

# -------------- Streamlit Interface --------------
st.set_page_config(page_title="Fiscalização Poda", page_icon="🌳")
st.title("🌳 Fiscalização Poda")

uploads = st.file_uploader("Carregar PDF ou ZIP", type=["pdf", "zip"], accept_multiple_files=True)

present_rows, absent_rows, exec_rows = [], [], []
counter = 0

if uploads:
    for up in uploads:
        ext = up.name.lower().split(".")[-1]
        if ext == "pdf":
            files = [(up.name, up.read())]
        else:
            files = []
            buf = io.BytesIO(up.read())
            with zipfile.ZipFile(buf) as zf:
                for n in zf.namelist():
                    if n.lower().endswith(".pdf"):
                        files.append((os.path.basename(n), zf.read(n)))

        for fname, data in files:
            counter += 1
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(data); path = tmp.name

            if "comunicacao" in fname.lower() and "execucao" in fname.lower():
                h, c, l, row = analisa_execucao(path)
                exec_rows.append(row)
                mostrar(h, c, l, key=f"exec_{counter}")
            else:
                h, c, l, status, row = analisa_fotos(path)
                mostrar(h, c, l, key=f"proj_{counter}")
                if status == "presentes":
                    present_rows.append(row)
                else:
                    absent_rows.append(row)
            os.remove(path)

# -------------- Excel export --------------
if present_rows or absent_rows or exec_rows:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        if present_rows:
            pd.DataFrame(present_rows).to_excel(writer, index=False, sheet_name="Fotos Presentes")
        if absent_rows:
            pd.DataFrame(absent_rows).to_excel(writer, index=False, sheet_name="Fotos Ausentes")
        if exec_rows:
            pd.DataFrame(exec_rows).to_excel(writer, index=False, sheet_name="Comunicação Execução")
    out.seek(0)
    st.download_button("Baixar Excel", data=out, file_name="resultados_poda.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
