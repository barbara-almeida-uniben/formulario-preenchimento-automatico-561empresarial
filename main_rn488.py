from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
import pandas as pd
from datetime import datetime
import calendar

# =====================================================
# LER PLANILHAS
# =====================================================

clientes = pd.read_excel(
    "dados.xlsx",
    sheet_name="Beneficiarios",
    dtype=str
).fillna("")

unimeds = pd.read_excel(
    "dados.xlsx",
    sheet_name="Unimed",
    dtype=str
).fillna("")

for coluna in clientes.columns:
    clientes[coluna] = clientes[coluna].astype(str).str.strip()

for coluna in unimeds.columns:
    unimeds[coluna] = unimeds[coluna].astype(str).str.strip()

# =====================================================
# ENTRADAS
# =====================================================

codigo = input("Digite o código do cliente: ").strip()

registro_produto = input("Digite o Nº de Registro do Produto: ").strip()

data_rescisao = input("Digite a data da rescisão do contrato de trabalho (DD/MM/AAAA): ").strip()

# =====================================================
# BUSCAR TITULAR
# =====================================================

cliente = clientes[
    (clientes["CODIGO"] == codigo) &
    (clientes["TIPO"] == "T")
]

if cliente.empty:
    print("Titular não encontrado.")
    exit()

row = cliente.iloc[0]

# =====================================================
# BUSCAR DEPENDENTES ATIVOS
# =====================================================

dependentes = clientes[
    (clientes["CODIGO"] == codigo) &
    (clientes["TIPO"] == "D") &
    (clientes["STATUS"] == "A")
]

dependentes_nomes = dependentes["NOME"].tolist()

# =====================================================
# BUSCAR UNIMED
# =====================================================

nome_unimed = str(row["OPERADORA"]).strip().upper()

unimeds["Unimed"] = unimeds["Unimed"].astype(str).str.strip().str.upper()

unimed = unimeds[
    unimeds["Unimed"].str.contains(nome_unimed, na=False, regex=False)
]

if unimed.empty:
    print("Unimed não encontrada.")
    print("Nome buscado:", nome_unimed)
    exit()

unimed_row = unimed.iloc[0]

# =====================================================
# DATAS AUTOMÁTICAS
# =====================================================

hoje = datetime.today()

data_solicitacao = hoje.strftime("%d/%m/%Y")

ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]

data_exclusao = f"{ultimo_dia:02d}/{hoje.month:02d}/{hoje.year}"

# =====================================================
# ABRIR PDF
# =====================================================

pdf = PdfReader("formulario_rn488.pdf")

if pdf.Root.AcroForm:
    pdf.Root.AcroForm.update(
        PdfDict(NeedAppearances=PdfObject("true"))
    )

# =====================================================
# CAMPOS PDF
# =====================================================

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

    # REGISTRO PRODUTO
    "Texto5": registro_produto,

    # DEPENDENTES
    "D1 Nome": dependentes_nomes[0] if len(dependentes_nomes) > 0 else "",
    "D2 Nome": dependentes_nomes[1] if len(dependentes_nomes) > 1 else "",
    "Texto14": dependentes_nomes[2] if len(dependentes_nomes) > 2 else "",
    "D4 Nome": dependentes_nomes[3] if len(dependentes_nomes) > 3 else "",

    # DATAS E INFORMAÇÕES
    "Data da rescisão do contrato de trabalho": data_rescisao,
    "Texto18": "Sócio-proprietário",
    "Texto19": "",
    "Texto20": data_solicitacao,
    "Texto4": data_exclusao,
}

# =====================================================
# PREENCHER PDF
# =====================================================

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

# =====================================================
# SALVAR PDF
# =====================================================

nome_pdf = f"RN488_{row['NOME']}.pdf"

PdfWriter().write(nome_pdf, pdf)

print(f"\nPDF RN488 gerado com sucesso: {nome_pdf}")