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

st.set_page_config(page_title="Proposta de Adesão", layout="centered")
st.title("📄 Gerador de Proposta de Adesão")

base_id = "1KcdNWj-qrvaHSoqKNEA0gNvwWzGuRQoD"

url_beneficiarios = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=2120607349"
url_unimed = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=912196708"
url_produtos = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=680489316"
url_lote_proposta = f"https://docs.google.com/spreadsheets/d/{base_id}/export?format=csv&gid=1170670471"


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
        "%m/%d/%Y",
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
        nascimento = datetime.strptime(data_nascimento, "%d/%m/%Y")
        hoje = datetime.today()

        idade = hoje.year - nascimento.year

        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1

        return idade

    except:
        return 0


def converter_valor(valor):
    valor = str(valor).replace(".", "").replace(",", ".")

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

    mes = str(mes).strip().replace(".0", "")
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
        (produto_base["Faixa-Inicio"] <= idade) &
        (produto_base["Faixa-Fim"] >= idade)
    ]

    if linha.empty:
        return 0.0

    return converter_valor(linha.iloc[0]["Valor"])


def buscar_unimed(row, unimeds):
    nome_operadora_cliente = str(row["OPERADORA"]).strip().upper()

    coluna_unimed = None

    for col in unimeds.columns:
        if col.strip().upper() == "UNIMED":
            coluna_unimed = col
            break

    if coluna_unimed is None:
        return None, None, "Coluna Unimed não encontrada."

    unimeds[coluna_unimed] = (
        unimeds[coluna_unimed]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    unimed = unimeds[
        unimeds[coluna_unimed].apply(
            lambda x: str(x).strip().upper() in nome_operadora_cliente
            or nome_operadora_cliente in str(x).strip().upper()
        )
    ]

    if unimed.empty:
        return None, None, f"Operadora não encontrada: {nome_operadora_cliente}"

    return unimed.iloc[0], coluna_unimed, None


clientes = limpar_df(pd.read_csv(url_beneficiarios, dtype=str))
unimeds = limpar_df(pd.read_csv(url_unimed, dtype=str))
produtos = limpar_df(pd.read_csv(url_produtos, dtype=str))

lista_produtos = sorted(produtos["Produto"].dropna().unique().tolist())


def gerar_proposta(
    codigo,
    tipo_processo,
    data_vigencia,
    produto_escolhido,
    cpf_novo_dependente="",
    nova_instituicao="",
    novo_cnpj_instituicao=""
):

    cliente = clientes[
        (clientes["CODIGO"] == str(codigo).strip()) &
        (clientes["TIPO"] == "T")
    ]

    if cliente.empty:
        return None, f"Titular não encontrado para o código {codigo}"

    row = cliente.iloc[0]

    if tipo_processo == "Inclusão de dependente":

        if not cpf_novo_dependente:
            return None, "CPF do novo dependente não informado."

        cpf_limpo = somente_digitos(cpf_novo_dependente, 11)

        dependentes = clientes[
            clientes["CPF"].apply(lambda x: somente_digitos(x, 11)) == cpf_limpo
        ]

        if dependentes.empty:
            return None, "Dependente não encontrado pelo CPF informado."

    else:

        dependentes = clientes[
            (clientes["CODIGO"] == str(codigo).strip()) &
            (clientes["TIPO"] == "D") &
            (clientes["STATUS"] == "A")
        ]

    produto_base = produtos[
        produtos["Produto"].str.strip().str.upper() == str(produto_escolhido).strip().upper()
    ]

    if produto_base.empty:
        return None, f"Produto não encontrado: {produto_escolhido}"

    produto_row = produto_base.iloc[0]

    unimed_row, coluna_unimed, erro_unimed = buscar_unimed(row, unimeds)

    if erro_unimed:
        return None, erro_unimed

    if tipo_processo == "Troca de instituição":
        instituicao = nova_instituicao
        cnpj_instituicao = somente_digitos(novo_cnpj_instituicao, 14)
    else:
        instituicao = row["INSTITUICAO"]
        cnpj_instituicao = somente_digitos(row["CNPJ_INSTITUICAO"], 14)

    if tipo_processo in ["Troca de produto", "Troca de instituição"]:
        carencia_titular = "sequência/troca"
        carencia_dependente = "sequência/troca"
    else:
        carencia_titular = "sequência"
        carencia_dependente = "sequência/troca"

    beneficiarios = []

    idade_titular = calcular_idade(row["DATA NASC."])
    valor_titular = buscar_valor_por_idade(produto_base, idade_titular)

    beneficiarios.append({
        "tipo": "Titular",
        "nome": row["NOME"],
        "cpf": somente_digitos(row["CPF"], 11),
        "rg": row["RG"],
        "data_nasc": formatar_data(row["DATA NASC."]),
        "mae": row["NOME DA MAE"],
        "parentesco": "TITULAR",
        "naturalidade": row["NATURALIDADE"],
        "sexo": row["SEXO"],
        "estado_civil": row["ESTADO CIVIL"],
        "idade": idade_titular,
        "valor": valor_titular,
        "carencia": carencia_titular
    })

    for _, dep in dependentes.iterrows():

        idade_dep = calcular_idade(dep["DATA NASC."])
        valor_dep = buscar_valor_por_idade(produto_base, idade_dep)

        beneficiarios.append({
            "tipo": "Dependente",
            "nome": dep["NOME"],
            "cpf": somente_digitos(dep["CPF"], 11),
            "rg": dep["RG"],
            "data_nasc": formatar_data(dep["DATA NASC."]),
            "mae": dep["NOME DA MAE"],
            "parentesco": dep["GRAU DE PARENTESCO"],
            "naturalidade": dep["NATURALIDADE"],
            "sexo": dep["SEXO"],
            "estado_civil": dep["ESTADO CIVIL"],
            "idade": idade_dep,
            "valor": valor_dep,
            "carencia": carencia_dependente
        })

    valor_total = sum(b["valor"] for b in beneficiarios)

    data_partes = str(data_vigencia).split("/")

    dia_vigencia = data_partes[0] if len(data_partes) > 0 else ""
    mes_vigencia = data_partes[1] if len(data_partes) > 1 else ""
    ano_vigencia = data_partes[2][-2:] if len(data_partes) > 2 else ""

    pdf = PdfReader("proposta_adesao.pdf")

    if pdf.Root.AcroForm:
        pdf.Root.AcroForm.update(
            PdfDict(NeedAppearances=PdfObject("true"))
        )
        pdf.Root.AcroForm.update(
            PdfDict(
                NeedAppearances=PdfObject("true"),
                DR=PdfDict()
            )
        )

    campos_pdf = {
        "Texto11": dia_vigencia,
        "Texto12": mes_vigencia,
        "Texto13": ano_vigencia,

        "Aglutinadora": instituicao,
        "CNPJ": cnpj_instituicao,

        "Operadora": unimed_row[coluna_unimed],
        "CNPJ_2": somente_digitos(unimed_row["CNPJ"], 14),
        "Registro ANS": unimed_row["ANS"],

        "Razão Social": row["EMPRESA"],
        "CNPJ_3": somente_digitos(row["CNPJ"], 14),
        "Modalidade": produto_row["Tipo Cont"],

        "Nome Completo": row["NOME"],
        "CPF": somente_digitos(row["CPF"], 11),
        "RG": row["RG"],
        "Data de Nascimento": formatar_data(row["DATA NASC."]),
        "Nome da Mãe": row["NOME DA MAE"],
        "Naturalidade": row["NATURALIDADE"],
        "Sexo": row["SEXO"],
        "Estado Civil": row["ESTADO CIVIL"],
        "Cartão Nacional de Saúde  CNS": "",
        "Carência": carencia_titular,

        "DDDTelefone Residencial": "",
        "DDDTelefone Celular": row["TELEFONE"],
        "Email": row["EMAIL"],

        "Nome Completo_2": "",
        "CPF_2": "",
        "RG_2": "",
        "Email_2": "",
        "Sexo_2": "",
        "Estado Civil_2": "",

        "Local Data": row["CIDADE"],
        "Titular Responsável Legal ou Financeiro": row["NOME"],

        "Plano": produto_row["Produto"],
        "Registro na ANS": produto_row["No. Registro"],

        "O mês de reajuste será": mes_por_extenso(produto_row["MesReajs"]),

        "Texto35": row["CIDADE"],
        "Texto36": datetime.today().strftime("%d/%m/%Y"),
        "Texto2": "Aline Abreu",
        "Texto3": row["NOME"],
        "Texto4": row["EMPRESA"],
    }

    dependente_campos = [
        {
            "nome": "Nome Completo_3",
            "cpf": "CPF_3",
            "rg": "RG_3",
            "data": "Data de Nascimento_2",
            "mae": "Nome da Mãe_2",
            "parentesco": "Parentesco",
            "naturalidade": "Naturalidade_2",
            "sexo": "Sexo_3",
            "estado": "Estado Civil_3",
            "cns": "Cartão Nacional de Saúde  CNS_2",
            "carencia": "Carência_2"
        },
        {
            "nome": "Nome Completo_4",
            "cpf": "CPF_4",
            "rg": "RG_4",
            "data": "Data de Nascimento_3",
            "mae": "Nome da Mãe_3",
            "parentesco": "Parentesco_2",
            "naturalidade": "Naturalidade_3",
            "sexo": "Sexo_4",
            "estado": "Estado Civil_4",
            "cns": "Cartão Nacional de Saúde  CNS_3",
            "carencia": "Carência_3"
        },
        {
            "nome": "Nome Completo_5",
            "cpf": "CPF_5",
            "rg": "RG_5",
            "data": "Data de Nascimento_4",
            "mae": "Nome da Mãe_4",
            "parentesco": "Parentesco_3",
            "naturalidade": "Naturalidade_4",
            "sexo": "Sexo_5",
            "estado": "Estado Civil_5",
            "cns": "Cartão Nacional de Saúde  CNS_4",
            "carencia": "Carência_4"
        },
        {
            "nome": "Nome Completo_6",
            "cpf": "CPF_6",
            "rg": "RG_6",
            "data": "Data de Nascimento_5",
            "mae": "Nome da Mãe_5",
            "parentesco": "Parentesco_4",
            "naturalidade": "Naturalidade_5",
            "sexo": "Sexo_6",
            "estado": "Estado Civil_6",
            "cns": "Cartão Nacional de Saúde  CNS_5",
            "carencia": "Carência_5"
        },
    ]

    dependentes_apenas = beneficiarios[1:]

    for i, dep in enumerate(dependentes_apenas[:4]):

        mapa = dependente_campos[i]

        campos_pdf[mapa["nome"]] = dep["nome"]
        campos_pdf[mapa["cpf"]] = dep["cpf"]
        campos_pdf[mapa["rg"]] = dep["rg"]
        campos_pdf[mapa["data"]] = dep["data_nasc"]
        campos_pdf[mapa["mae"]] = dep["mae"]
        campos_pdf[mapa["parentesco"]] = dep["parentesco"]
        campos_pdf[mapa["naturalidade"]] = dep["naturalidade"]
        campos_pdf[mapa["sexo"]] = dep["sexo"]
        campos_pdf[mapa["estado"]] = dep["estado_civil"]
        campos_pdf[mapa["cns"]] = ""
        campos_pdf[mapa["carencia"]] = dep["carencia"]

    valores_pagina4 = [
        ("IdadeTitular", "R"),
        ("IdadeDependente 1", "R_3"),
        ("IdadeDependente 2", "R_5"),
        ("IdadeDependente 3", "R_7"),
        ("IdadeDependente 4", "R_9"),
    ]

    for i, b in enumerate(beneficiarios[:5]):

        campo_idade, campo_mensalidade = valores_pagina4[i]

        campos_pdf[campo_idade] = str(b["idade"])
        campos_pdf[campo_mensalidade] = formatar_moeda(b["valor"])

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
                valor = str(campos_pdf[campo])

                annotation.update(
                    PdfDict(
                        V=valor,
                        AS=valor,
                        AP=None  # remove aparência travada
                    )
                )

    packet = BytesIO()

    largura = float(pdf.pages[0].MediaBox[2])
    altura = float(pdf.pages[0].MediaBox[3])

    can = canvas.Canvas(packet, pagesize=(largura, altura))

    can.setFont("Helvetica", 10)

    # Página 1 - endereço do titular
    can.drawString(295, 281, str(row["ENDERECO"]))          # Endereço
    can.drawString(35, 250, str(row["NUMERO"]))             # Número
    can.drawString(145, 245, str(row["COMPLEMENTO"]))       # Complemento
    can.drawString(300, 250, str(row["BAIRRO"]))            # Bairro
    can.drawString(35, 215, str(row["CIDADE"]))             # Município
    can.drawString(385, 215, somente_digitos(row["CEP"], 8))# CEP
    can.drawString(500, 215, str(row["UF"]))                # UF

    can.showPage()
    can.showPage()
    can.showPage()

    can.setFont("Helvetica-Bold", 9)
    can.drawString(248, 502, formatar_moeda(valor_total))

    can.save()

    packet.seek(0)

    overlay_pdf = PdfReader(packet)

    PageMerge(pdf.pages[0]).add(overlay_pdf.pages[0]).render()

    if len(overlay_pdf.pages) > 3:
        PageMerge(pdf.pages[3]).add(overlay_pdf.pages[3]).render()

    nome_pdf_final = f"Proposta_Adesao_{codigo}_{nome_seguro(row['NOME'])}.pdf"

    PdfWriter().write(nome_pdf_final, pdf)

    return nome_pdf_final, None


modo = st.radio(
    "Como deseja gerar?",
    ["Individual", "Lote - Troca de produto"]
)

if modo == "Individual":

    codigo = st.text_input("Digite o código do cliente titular")

    tipo_processo = st.selectbox(
        "Tipo de processo",
        [
            "Troca de produto",
            "Troca de instituição",
            "Inclusão de dependente"
        ]
    )

    data_vigencia = st.text_input("Data de vigência - DD/MM/AA")

    produto_escolhido = st.selectbox(
        "Produto / Plano",
        lista_produtos
    )

    cpf_novo_dependente = ""

    if tipo_processo == "Inclusão de dependente":
        cpf_novo_dependente = st.text_input("CPF do novo dependente")

    nova_instituicao = ""
    novo_cnpj_instituicao = ""

    if tipo_processo == "Troca de instituição":
        nova_instituicao = st.text_input("Nova instituição")
        novo_cnpj_instituicao = st.text_input("CNPJ da nova instituição")

    if st.button("Gerar proposta"):

        arquivo_pdf, erro = gerar_proposta(
            codigo,
            tipo_processo,
            data_vigencia,
            produto_escolhido,
            cpf_novo_dependente,
            nova_instituicao,
            novo_cnpj_instituicao
        )

        if erro:
            st.error(erro)

        else:

            st.success("Proposta gerada com sucesso!")

            with open(arquivo_pdf, "rb") as file:
                st.download_button(
                    label="⬇️ Baixar proposta",
                    data=file,
                    file_name=arquivo_pdf,
                    mime="application/pdf"
                )

else:

    st.info("O modo lote lê a aba Lote_Proposta.")
    st.write("A aba deve conter: CODIGO | DATA_VIGENCIA | PRODUTO")

    if st.button("Gerar propostas em lote"):

        lote = limpar_df(
            pd.read_csv(url_lote_proposta, dtype=str)
        )

        pasta_saida = "Propostas_Adesao"

        os.makedirs(pasta_saida, exist_ok=True)

        for arquivo_antigo in os.listdir(pasta_saida):

            caminho_antigo = os.path.join(
                pasta_saida,
                arquivo_antigo
            )

            if os.path.isfile(caminho_antigo):
                os.remove(caminho_antigo)

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
                erros.append(f"{codigo}: {erro}")
                continue

            novo_caminho = os.path.join(
                pasta_saida,
                arquivo_pdf
            )

            os.replace(arquivo_pdf, novo_caminho)

            arquivos_gerados.append(novo_caminho)

        if not arquivos_gerados:
            st.error("Nenhuma proposta foi gerada.")

            if erros:
                st.write(erros)

        else:

            nome_zip = f"Propostas_Adesao_{datetime.today().strftime('%Y%m%d_%H%M%S')}.zip"

            with zipfile.ZipFile(nome_zip, "w") as zipf:

                for arquivo in arquivos_gerados:
                    zipf.write(
                        arquivo,
                        arcname=os.path.basename(arquivo)
                    )

            st.success(
                f"{len(arquivos_gerados)} proposta(s) gerada(s)!"
            )

            if erros:
                st.warning("Alguns registros tiveram erro:")
                st.write(erros)

            with open(nome_zip, "rb") as file:
                st.download_button(
                    label="⬇️ Baixar ZIP",
                    data=file,
                    file_name=nome_zip,
                    mime="application/zip"
                )