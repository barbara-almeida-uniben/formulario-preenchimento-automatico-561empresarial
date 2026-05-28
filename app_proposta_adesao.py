import streamlit as st
import pandas as pd
from pdfrw import PdfReader, PdfWriter, PdfDict, PageMerge
from pdfrw.objects.pdfobject import PdfObject
from reportlab.pdfgen import canvas
from datetime import datetime
from io import BytesIO
import re
import os
import zipfile

st.set_page_config(
    page_title="Proposta de Adesão",
    layout="centered"
)

st.title("📄 Gerador de Proposta de Adesão")

# =====================================================
# LINKS
# =====================================================

base_id = "1KcdNWj-qrvaHSoqKNEA0gNvwWzGuRQoD"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=2120607349"

url_unimed = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=912196708"

url_produtos = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=680489316"

url_lote_proposta = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=1170670471"

# =====================================================
# FUNCOES
# =====================================================

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


def formatar_data(valor):

    valor = str(valor).strip()

    formatos = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d"
    ]

    for formato in formatos:

        try:

            data = datetime.strptime(valor, formato)

            return data.strftime("%d/%m/%Y")

        except:
            pass

    return valor


def calcular_idade(data_nascimento):

    data_nascimento = formatar_data(data_nascimento)

    try:

        nascimento = datetime.strptime(
            data_nascimento,
            "%d/%m/%Y"
        )

        hoje = datetime.today()

        idade = hoje.year - nascimento.year

        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1

        return idade

    except:

        return 0


def converter_valor(valor):

    valor = str(valor)

    valor = valor.replace(".", "").replace(",", ".")

    try:

        return float(valor)

    except:

        return 0.0


def formatar_moeda(valor):

    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_por_extenso(mes):

    meses = {
        "1": "Janeiro",
        "2": "Fevereiro",
        "3": "Março",
        "4": "Abril",
        "5": "Maio",
        "6": "Junho",
        "7": "Julho",
        "8": "Agosto",
        "9": "Setembro",
        "10": "Outubro",
        "11": "Novembro",
        "12": "Dezembro",
    }

    mes = str(mes).replace(".0", "").strip()

    return meses.get(mes, mes)


def buscar_valor_por_idade(produto_base, idade):

    produto_base = produto_base.copy()

    produto_base["Faixa-Inicio"] = (
        produto_base["Faixa-Inicio"]
        .astype(str)
        .str.replace(",", ".")
        .astype(float)
    )

    produto_base["Faixa-Fim"] = (
        produto_base["Faixa-Fim"]
        .astype(str)
        .str.replace(",", ".")
        .astype(float)
    )

    linha = produto_base[
        (produto_base["Faixa-Inicio"] <= idade)
        &
        (produto_base["Faixa-Fim"] >= idade)
    ]

    if linha.empty:
        return 0.0

    return converter_valor(
        linha.iloc[0]["Valor"]
    )


def buscar_unimed(row, unimeds):

    nome_operadora_cliente = str(
        row["OPERADORA"]
    ).strip().upper()

    coluna_unimed = None

    for col in unimeds.columns:

        if col.strip().upper() == "Unimed":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        return None, "Coluna Unimed não encontrada."

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed].apply(
            lambda x:
            x in nome_operadora_cliente
            or nome_operadora_cliente in x
        )
    ]

    if unimed.empty:

        return None, f"Operadora não encontrada: {nome_operadora_cliente}"

    return unimed.iloc[0], None

# =====================================================
# BASES
# =====================================================

clientes = limpar_df(
    pd.read_csv(url_beneficiarios, dtype=str)
)

unimeds = limpar_df(
    pd.read_csv(url_unimed, dtype=str)
)

produtos = limpar_df(
    pd.read_csv(url_produtos, dtype=str)
)

lista_produtos = sorted(
    produtos["Produto"].dropna().unique().tolist()
)

# =====================================================
# FUNCAO GERAR PROPOSTA
# =====================================================

def gerar_proposta(
    codigo,
    tipo_processo,
    data_vigencia,
    produto_escolhido
):

    cliente = clientes[
        (clientes["CODIGO"] == str(codigo).strip())
        &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        return None, "Titular não encontrado."

    row = cliente.iloc[0]

    dependentes = clientes[
        (clientes["CODIGO"] == str(codigo).strip())
        &
        (clientes["TIPO"] == "D")
        &
        (clientes["STATUS"] == "A")
    ]

    produto_base = produtos[
        produtos["Produto"].str.strip().str.upper()
        ==
        str(produto_escolhido).strip().upper()
    ]

    if produto_base.empty:
        return None, "Produto não encontrado."

    produto_row = produto_base.iloc[0]

    unimed_row, erro_unimed = buscar_unimed(
        row,
        unimeds
    )

    if erro_unimed:
        return None, erro_unimed

    beneficiarios = []

    idade_titular = calcular_idade(
        row["DATA NASC."]
    )

    valor_titular = buscar_valor_por_idade(
        produto_base,
        idade_titular
    )

    beneficiarios.append({
        "nome": row["NOME"],
        "idade": idade_titular,
        "valor": valor_titular
    })

    for _, dep in dependentes.iterrows():

        idade_dep = calcular_idade(
            dep["DATA NASC."]
        )

        valor_dep = buscar_valor_por_idade(
            produto_base,
            idade_dep
        )

        beneficiarios.append({
            "nome": dep["NOME"],
            "idade": idade_dep,
            "valor": valor_dep
        })

    valor_total = sum(
        b["valor"] for b in beneficiarios
    )

    pdf = PdfReader("proposta_adesao.pdf")

    if pdf.Root.AcroForm:

        pdf.Root.AcroForm.update(
            PdfDict(
                NeedAppearances=PdfObject("true")
            )
        )

    campos_pdf = {

        "Aglutinadora": row["INSTITUICAO"],

        "Operadora": unimed_row["UNIMED"],

        "Registro ANS": unimed_row["ANS"],

        "Razão Social": row["EMPRESA"],

        "Nome Completo": row["NOME"],

        "CPF": somente_digitos(
            row["CPF"],
            11
        ),

        "RG": row["RG"],

        "Data de Nascimento": formatar_data(
            row["DATA NASC."]
        ),

        "Nome da Mãe": row["NOME DA MAE"],

        "Naturalidade": row["NATURALIDADE"],

        "Sexo": row["SEXO"],

        "Estado Civil": row["ESTADO CIVIL"],

        "DDDTelefone Celular": row["TELEFONE"],

        "Email": row["EMAIL"],

        "Plano": produto_row["Produto"],

        "O mês de reajuste será": mes_por_extenso(
            produto_row["MesReajs"]
        ),

        "Texto35": row["CIDADE"],

        "Texto36": datetime.today().strftime("%d/%m/%Y"),

        "Texto2": "Aline Abreu",

        "Texto3": row["NOME"],

        "Texto4": row["EMPRESA"]
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

            if campo in campos_pdf:

                annotation.update(
                    PdfDict(
                        V=str(campos_pdf[campo])
                    )
                )

    packet = BytesIO()

    largura = float(pdf.pages[0].MediaBox[2])
    altura = float(pdf.pages[0].MediaBox[3])

    can = canvas.Canvas(
        packet,
        pagesize=(largura, altura)
    )

    can.setFont("Helvetica", 7)

    can.drawString(295, 281, str(row["ENDERECO"]))
    can.drawString(35, 258, str(row["NUMERO"]))
    can.drawString(125, 258, str(row["COMPLEMENTO"]))
    can.drawString(260, 258, str(row["BAIRRO"]))
    can.drawString(35, 235, str(row["CIDADE"]))
    can.drawString(365, 235, somente_digitos(row["CEP"], 8))
    can.drawString(510, 235, str(row["UF"]))

    can.showPage()
    can.showPage()
    can.showPage()

    can.setFont("Helvetica-Bold", 9)

    can.drawString(
        248,
        502,
        formatar_moeda(valor_total)
    )

    can.save()

    packet.seek(0)

    overlay_pdf = PdfReader(packet)

    PageMerge(pdf.pages[0]).add(
        overlay_pdf.pages[0]
    ).render()

    if len(overlay_pdf.pages) > 3:

        PageMerge(pdf.pages[3]).add(
            overlay_pdf.pages[3]
        ).render()

    nome_pdf_final = (
        f"Proposta_"
        f"{codigo}_"
        f"{nome_seguro(row['NOME'])}.pdf"
    )

    PdfWriter().write(
        nome_pdf_final,
        pdf
    )

    return nome_pdf_final, None

# =====================================================
# INTERFACE
# =====================================================

modo = st.radio(
    "Como deseja gerar?",
    [
        "Individual",
        "Lote - Troca de produto"
    ]
)

# =====================================================
# INDIVIDUAL
# =====================================================

if modo == "Individual":

    codigo = st.text_input(
        "Código do cliente"
    )

    tipo_processo = st.selectbox(
        "Tipo de processo",
        [
            "Troca de produto"
        ]
    )

    data_vigencia = st.text_input(
        "Data vigência DD/MM/AA"
    )

    produto_escolhido = st.selectbox(
        "Produto",
        lista_produtos
    )

    if st.button("Gerar proposta"):

        arquivo_pdf, erro = gerar_proposta(
            codigo,
            tipo_processo,
            data_vigencia,
            produto_escolhido
        )

        if erro:

            st.error(erro)

        else:

            st.success(
                "Proposta gerada com sucesso!"
            )

            with open(arquivo_pdf, "rb") as file:

                st.download_button(
                    label="⬇️ Baixar proposta",
                    data=file,
                    file_name=arquivo_pdf,
                    mime="application/pdf"
                )

# =====================================================
# LOTE
# =====================================================

else:

    st.info(
        "Modo lote pela aba Lote_Proposta"
    )

    if st.button("Gerar propostas em lote"):

        lote = limpar_df(
            pd.read_csv(
                url_lote_proposta,
                dtype=str
            )
        )

        pasta_saida = "Propostas_Adesao"

        os.makedirs(
            pasta_saida,
            exist_ok=True
        )

        arquivos_gerados = []

        erros = []

        for _, item in lote.iterrows():

            codigo = item["CODIGO"].strip()

            data_vigencia = item["DATA_VIGENCIA"].strip()

            produto_escolhido = item["PRODUTO"].strip()

            arquivo_pdf, erro = gerar_proposta(
                codigo,
                "Troca de produto",
                data_vigencia,
                produto_escolhido
            )

            if erro:

                erros.append(
                    f"{codigo}: {erro}"
                )

                continue

            novo_caminho = os.path.join(
                pasta_saida,
                arquivo_pdf
            )

            os.replace(
                arquivo_pdf,
                novo_caminho
            )

            arquivos_gerados.append(
                novo_caminho
            )

        if not arquivos_gerados:

            st.error(
                "Nenhuma proposta gerada."
            )

            st.write(erros)

        else:

            nome_zip = "Propostas_Adesao.zip"

            with zipfile.ZipFile(
                nome_zip,
                "w"
            ) as zipf:

                for arquivo in arquivos_gerados:

                    zipf.write(
                        arquivo,
                        arcname=os.path.basename(arquivo)
                    )

            st.success(
                f"{len(arquivos_gerados)} proposta(s) gerada(s)"
            )

            with open(nome_zip, "rb") as file:

                st.download_button(
                    label="⬇️ Baixar ZIP",
                    data=file,
                    file_name=nome_zip,
                    mime="application/zip"
                )