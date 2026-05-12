from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
import pandas as pd
from datetime import datetime
import calendar
import os
import re

# =========================
# LINKS GOOGLE SHEETS
# =========================

base_id = "1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/gviz/tq?tqx=out:csv&sheet=Beneficiarios"
url_unimed = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=483371263"
url_lote = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=448530069"

# =========================
# LER BASES
# =========================

clientes = pd.read_csv(url_beneficiarios, dtype=str).fillna("")
unimeds = pd.read_csv(url_unimed, dtype=str).fillna("")
lote = pd.read_csv(url_lote, dtype=str).fillna("")

for df in [clientes, unimeds, lote]:
    df.columns = df.columns.str.strip()
    for coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.strip()

# =========================
# DATAS AUTOMÁTICAS
# =========================

hoje = datetime.today()
data_solicitacao = hoje.strftime("%d/%m/%Y")
ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
data_exclusao = f"{ultimo_dia:02d}/{hoje.month:02d}/{hoje.year}"

# =========================
# PASTA DE SAÍDA
# =========================

pasta_saida = "PDFs_RN488"
os.makedirs(pasta_saida, exist_ok=True)

def nome_seguro(texto):
    return re.sub(r'[\\/*?:"<>|]', "-", texto)

# =========================
# PROCESSAR LOTE
# =========================

for _, item in lote.iterrows():

    codigo = item["CODIGO"]
    registro_produto = item["REGISTRO_PRODUTO"]
    data_rescisao = item["DATA_RESCISAO"]

    cliente = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        print(f"Titular não encontrado para código {codigo}")
        continue

    row = cliente.iloc[0]

    dependentes = clientes[
        (clientes["CODIGO"] == codigo) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

    dependentes_nomes = dependentes["NOME"].tolist()

    nome_unimed = str(row["OPERADORA"]).strip().upper()

    unimeds["Unimed"] = unimeds["Unimed"].astype(str).str.strip().str.upper()

    unimed = unimeds[
        unimeds["Unimed"].str.contains(nome_unimed, na=False, regex=False)
    ]

    if unimed.empty:
        print(f"Unimed não encontrada para {row['NOME']} - {nome_unimed}")
        continue

    unimed_row = unimed.iloc[0]

    pdf = PdfReader("formulario_rn488.pdf")

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(
            PdfDict(NeedAppearances=PdfObject("true"))
        )

    campos_pdf = {
        # OPERADORA
        "Texto1": unimed_row["Unimed"],
        "Texto2": unimed_row["CNPJ"],
        "Texto3": unimed_row["ANS"],

        # CONTRATANTE
        "Razão Social": row["EMPRESA"],
        "CNPJ": row["CNPJ"],

        # TITULAR
        "Texto6": row["NOME"],
        "Texto7": row["CPF"],

        # REGISTRO DO PRODUTO
        "Texto5": registro_produto,

        # DEPENDENTES
        "D1 Nome": dependentes_nomes[0] if len(dependentes_nomes) > 0 else "",
        "D2 Nome": dependentes_nomes[1] if len(dependentes_nomes) > 1 else "",
        "Texto14": dependentes_nomes[2] if len(dependentes_nomes) > 2 else "",
        "D4 Nome": dependentes_nomes[3] if len(dependentes_nomes) > 3 else "",

        # DATAS
        "Data da rescisão do contrato de trabalho": data_rescisao,
        "Texto18": "Sócio-proprietário",
        "Texto19": "",
        "Texto20": data_solicitacao,
        "Texto4": data_exclusao,
    }

    for page in pdf.pages:
        annotations = page.get("/Annots")

        if not annotations:
            continue

        for annotation in annotations:
            if annotation.get("/Subtype") != "/Widget":
                continue

            key = annotation.get("/T")

            if not key:
                continue

            campo = key[1:-1]

            if "Check Box" in campo:
                continue

            if campo in campos_pdf:
                annotation.update(
                    PdfDict(V=str(campos_pdf[campo]))
                )

    nome_pdf = f"RN488_{codigo}_{nome_seguro(row['NOME'])}.pdf"
    caminho_pdf = os.path.join(pasta_saida, nome_pdf)

    PdfWriter().write(caminho_pdf, pdf)

    print(f"PDF gerado: {nome_pdf}")

print("\nProcessamento em lote finalizado!")