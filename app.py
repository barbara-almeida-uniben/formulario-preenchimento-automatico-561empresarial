import streamlit as st
import pandas as pd
from pdfrw import PdfReader, PdfWriter, PdfDict
from pdfrw.objects.pdfobject import PdfObject
import re

st.set_page_config(
    page_title="Formulário 561",
    layout="centered"
)

st.title("📄 Gerador de Formulário 561")

base_id = "1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ"

url_beneficiarios = (
    "https://docs.google.com/spreadsheets/d/"
    "1LjKHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=2120607349"
)
url_unimed = "https://docs.google.com/spreadsheets/d/1LjkHRoSQElthQYiyMzv8vjAtuJDhx6yQ/export?format=csv&gid=483371263"


def limpar_df(df):
    df = df.fillna("")
    df.columns = df.columns.astype(str).str.strip()

    for coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.strip()

    return df


def somente_digitos(valor, tamanho=None):
    valor = "" if pd.isna(valor) else str(valor)
    valor = "".join(filter(str.isdigit, valor))

    if tamanho:
        valor = valor.zfill(tamanho)

    return valor


def nome_seguro(texto):
    return re.sub(r'[\\/*?:"<>|]', "-", str(texto))


clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))
unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))

codigo = st.text_input("Digite o código do cliente")

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

motivo = st.selectbox(
    "Motivo do cancelamento",
    list(motivos.keys()),
    format_func=lambda x: f"{x} - {motivos[x]}"
)

if st.button("Gerar PDF"):

    cliente = clientes[
        (clientes["CODIGO"] == codigo.strip()) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        st.error("Titular não encontrado.")
        st.stop()

    row = cliente.iloc[0]

    dependentes = clientes[
        (clientes["CODIGO"] == codigo.strip()) &
        (clientes["TIPO"] == "D") &
        (clientes["STATUS"] == "A")
    ]

    beneficiarios = [row["NOME"]]

    for _, dep in dependentes.iterrows():
        beneficiarios.append(dep["NOME"])

    nome_unimed = str(row["OPERADORA"]).strip().upper()

    unimeds.columns = unimeds.columns.astype(str).str.strip()

    coluna_unimed = None

    for col in unimeds.columns:
        if col.strip().upper() == "UNIMED":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        st.error("Coluna 'Unimed' não encontrada na aba Unimed.")
        st.write("Colunas encontradas:", unimeds.columns.tolist())
        st.stop()

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed].str.contains(nome_unimed, na=False, regex=False)
    ]

    if unimed.empty:
        st.error("Unimed não encontrada.")
        st.write("Nome buscado:", nome_unimed)
        st.write("Unimeds cadastradas:", unimeds[coluna_unimed].tolist())
        st.stop()

    unimed_row = unimed.iloc[0]

    pdf = PdfReader("formulario.pdf")

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(
            PdfDict(NeedAppearances=PdfObject("true"))
        )

    campos_pdf = {
        "Texto3": unimed_row[coluna_unimed],
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

    nome_pdf = f"Formulario_561_{codigo}_{nome_seguro(row['NOME'])}.pdf"

    PdfWriter().write(nome_pdf, pdf)

    st.success("PDF gerado com sucesso!")

    with open(nome_pdf, "rb") as file:
        st.download_button(
            label="⬇️ Baixar PDF",
            data=file,
            file_name=nome_pdf,
            mime="application/pdf"
        )