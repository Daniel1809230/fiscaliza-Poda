import streamlit as st
import fitz
import os

st.set_page_config(page_title="Fiscalização Poda", page_icon="🌳")
st.title("🌳 Fiscalização Poda")
st.caption("Criado por Daniel Martins Moraes")

uploaded_files = st.file_uploader("CarregarPDF", type="pdf", accept_multiple_files=True)

def extrair_infos(pdf_path):
    doc = fitz.open(pdf_path)
    resultados = []
    for page_num, page in enumerate(doc, start=1):
        blocos = page.get_text("dict")["blocks"]
        textos = []
        imagens = []
        codigos_encontrados = []
        for b in blocos:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        texto = span["text"].strip().lower()
                        if any(k in texto for k in ["foto inspeção", "foto execução", "foto antes da recolha", "foto depois da recolha"]):
                            textos.append({
                                "tipo": texto,
                                "x": span["bbox"][0],
                                "y": span["bbox"][1]
                            })
                        elif texto.startswith("código") or texto.startswith("codigo"):
                            partes = texto.replace(":", "").split()
                            for parte in partes:
                                if parte.isdigit():
                                    codigos_encontrados.append(int(parte))
        if not codigos_encontrados:
            codigos_encontrados = list(range(1, 100))

        for b in blocos:
            if "image" in b:
                imagens.append({
                    "xref": b["image"],
                    "x": b["bbox"][0],
                    "y": b["bbox"][1]
                })

        grupos = []
        for idx, t in enumerate(textos):
            tipo = t["tipo"].replace("foto ", "").capitalize()
            cod = codigos_encontrados[idx // 4] if idx // 4 < len(codigos_encontrados) else idx // 4 + 1
            correspondente = next((img for img in imagens if img["y"] > t["y"] and abs(img["x"] - t["x"]) <= 50 and 0 < img["y"] - t["y"] <= 200), None)
            grupos.append({
                "codigo": cod,
                "tipo_foto": tipo,
                "presente": correspondente is not None
            })

        agrupado = {}
        for g in grupos:
            if g["codigo"] not in agrupado:
                agrupado[g["codigo"]] = []
            agrupado[g["codigo"]].append(g)

        nome_proj = os.path.basename(pdf_path).split("_")[0]
        total_faltantes = []
        for codigo, lista in agrupado.items():
            faltando = [g["tipo_foto"] for g in lista if not g["presente"]]
            if faltando:
                total_faltantes.append((codigo, faltando))

        if total_faltantes:
            saida = f"📍 Projeto: {nome_proj} — fotos ausentes"
            for cod, faltas in total_faltantes:
                tipos = ", ".join(faltas)
                saida += f"\n→ codigo {cod} : ausentes — {tipos}"
        else:
            saida = f"📍 Projeto: {nome_proj} — todas as fotos estão presentes"
        resultados.append(saida)
    return "\n\n".join(resultados)

if uploaded_files:
    for f in uploaded_files:
        with open(f.name, "wb") as buffer:
            buffer.write(f.read())
        resultado = extrair_infos(f.name)
        st.text_area("Resultado", resultado, height=200)
        os.remove(f.name)
