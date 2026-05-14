from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
import pandas as pd

clientes = pd.read_excel("dados.xlsx", sheet_name="Beneficiarios", dtype=str).fillna("")
unimeds = pd.read_excel("dados.xlsx", sheet_name="Unimed", dtype=str).fillna("")

for coluna in clientes.columns:
    clientes[coluna] = clientes[coluna].astype(str).str.strip()

for coluna in unimeds.columns:
    unimeds[coluna] = unimeds[coluna].astype(str).str.strip()

def somente_digitos(valor, tamanho=None):
    valor = "" if pd.isna(valor) else str(valor)
    valor = "".join(filter(str.isdigit, valor))

    if tamanho:
        valor = valor.zfill(tamanho)

    return valor

codigo = input("Digite o código do cliente: ").strip()

cliente = clientes[
    (clientes["CODIGO"] == codigo) &
    (clientes["TIPO"] == "T")
]

if cliente.empty:
    print("Titular não encontrado.")
    exit()

row = cliente.iloc[0]

dependentes = clientes[
    (clientes["CODIGO"] == codigo) &
    (clientes["TIPO"] == "D") &
    (clientes["STATUS"] == "A")
]

motivos = {
    "76": "Óbito",
    "64": "Não usa o plano",
    "58": "Migração para outra operadora",
    "60": "Insatisfeito com o atendimento do plano",
    "95": "Pessoal",
    "82": "Financeiro",
    "75": "Troca na mesma Unimed",
    "56": "Viagem/Mudança"
}

print("\nQual o motivo do cancelamento?\n")

for cod, desc in motivos.items():
    print(f"{cod} - {desc}")

motivo = input("\nDigite o código do motivo: ").strip()

if motivo not in motivos:
    print("Motivo inválido.")
    exit()

nome_unimed = row["OPERADORA"].strip().upper()

unimeds["Unimed"] = unimeds["Unimed"].astype(str).str.strip().str.upper()

unimed = unimeds[
    unimeds["Unimed"].str.contains(nome_unimed, na=False, regex=False)
]

if unimed.empty:
    print("Unimed não encontrada.")
    exit()

unimed_row = unimed.iloc[0]

beneficiarios = [row["NOME"]]

for _, dep in dependentes.iterrows():
    beneficiarios.append(dep["NOME"])

pdf = PdfReader("formulario.pdf")

if pdf.Root.AcroForm:
    pdf.Root.AcroForm.update(
        PdfDict(NeedAppearances=PdfObject("true"))
    )

campos_pdf = {
    "Texto3": unimed_row["Unimed"],
    "Texto4": somente_digitos(unimed_row["CNPJ"], 14),
    "Texto5": unimed_row["ANS"],

    "Texto42": row["INSTITUICAO"],
    "Texto43": somente_digitos(row["CNPJ_INSTITUICAO"], 14),

    "Razão Social": row["EMPRESA"],
    "CNPJ": somente_digitos(row["CNPJ"], 14),

    "Texto7": row["NOME"],
    "Texto8": somente_digitos(row["CPF"], 11),
    "Texto9": row["EMAIL"],

    "Texto10": row["ENDERECO"],
    "Texto11": row["NUMERO"],

    "Bairro": row["COMPLEMENTO"],
    "Texto12": row["BAIRRO"],

    "Texto13": row["CIDADE"],
    "UF": row["UF"],
    "CEP": somente_digitos(row["CEP"], 8),

    "DDD  Telefone Celular": row["TELEFONE"],

    "Texto16": motivo,
    "Texto18": beneficiarios[0] if len(beneficiarios) > 0 else "",

    "Texto20": motivo if len(beneficiarios) > 1 else "",
    "Texto22": beneficiarios[1] if len(beneficiarios) > 1 else "",

    "Texto24": motivo if len(beneficiarios) > 2 else "",
    "Texto26": beneficiarios[2] if len(beneficiarios) > 2 else "",

    "Texto28": motivo if len(beneficiarios) > 3 else "",
    "Texto30": beneficiarios[3] if len(beneficiarios) > 3 else "",

    "Texto32": motivo if len(beneficiarios) > 4 else "",
    "Texto34": beneficiarios[4] if len(beneficiarios) > 4 else "",

    "estou ciente das informações acima prestadas e manifesto a minha vontade em": row["NOME"],
    "undefined_4": somente_digitos(row["CPF"], 11),

    "Texto1": beneficiarios[0] if len(beneficiarios) > 0 else "",
    "Texto2": beneficiarios[1] if len(beneficiarios) > 1 else "",

    "Nomes": beneficiarios[0] if len(beneficiarios) > 0 else "",
    "undefined_11": beneficiarios[1] if len(beneficiarios) > 1 else "",
    "undefined_12": beneficiarios[2] if len(beneficiarios) > 2 else "",
    "undefined_13": beneficiarios[3] if len(beneficiarios) > 3 else "",

    "Nomes_2": beneficiarios[4] if len(beneficiarios) > 4 else "",
    "undefined_14": beneficiarios[5] if len(beneficiarios) > 5 else "",
    "undefined_15": beneficiarios[6] if len(beneficiarios) > 6 else "",
    "undefined_16": beneficiarios[7] if len(beneficiarios) > 7 else "",
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

        if "Check Box" in campo or "Group" in campo:
            continue

        if campo in campos_pdf:
            annotation.update(
                PdfDict(V=str(campos_pdf[campo]))
            )

nome_pdf = f"{row['NOME']}.pdf"

PdfWriter().write(nome_pdf, pdf)

print(f"\nPDF gerado com sucesso: {nome_pdf}")