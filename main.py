import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import StringIO, BytesIO


# Função para padronizar datas para o primeiro dia do mês
@st.cache_data(show_spinner=False)
def padronizar_periodo(df):
    df['AnoMes'] = pd.to_datetime(df['DT_RETIRADA_RA']).dt.to_period('M').dt.to_timestamp()
    return df


def preprocess(df):
    df.columns = df.columns.str.strip()
    df = df[~df.apply(lambda row: row.astype(str).str.contains("cadastro", case=False).any(), axis=1)]

    df = df.rename(columns={
        "Nm_Preposto_1": "PREPOSTO",
        "Locatario": "LOCATARIO"
    })

    df["DT_RETIRADA_RA"] = pd.to_datetime(df["DT_RETIRADA_RA"], dayfirst=True, errors="coerce")
    df["DT_DEVOLUCAO_RA"] = pd.to_datetime(df["DT_DEVOLUCAO_RA"], dayfirst=True, errors="coerce")

    def to_float(x):
        try:
            if isinstance(x, str):
                return float(x.replace("R$", "").replace(".", "").replace(",", ".").strip())
            return float(x)
        except:
            return np.nan

    campos_valor = [
        "TARIFA", "SUB_TOTAL", "TOTAL_RA", "TX_RETORNO", "DESPESAS",
        "ADICIONAIS", "TX_SERVICO", "TOTAL_PROT", "TOTAL_HORA_EXTRA", "PART_OBRIGATORIA",
        "RECUPERACAO_AVARIAS", "REEMBOLSO", "TOTAL_DESCON", "COMBUSTIVEL"
    ]

    alertas = []
    for campo in campos_valor:
        if campo in df.columns:
            original_na = df[campo].isna().sum()
            df[campo] = df[campo].apply(to_float)
            convertido_na = df[campo].isna().sum()
            if convertido_na > original_na:
                alertas.append(f"Campo '{campo}': {convertido_na - original_na} valores não numéricos convertidos para NaN.")

    def to_km(x):
        try:
            if isinstance(x, str):
                return float(x.replace(".", "").replace(",", ".").strip())
            return float(x)
        except:
            return np.nan

    for campo in ["Km_Retirada", "Km_Devolucao"]:
        if campo in df.columns:
            original_na = df[campo].isna().sum()
            df[campo] = df[campo].apply(to_km)
            convertido_na = df[campo].isna().sum()
            if convertido_na > original_na:
                alertas.append(f"Campo '{campo}': {convertido_na - original_na} valores não numéricos convertidos para NaN.")

    df["KM_RODADO"] = df["Km_Devolucao"] - df["Km_Retirada"]
    df["Ano"] = df["DT_RETIRADA_RA"].dt.year
    df["Mes"] = df["DT_RETIRADA_RA"].dt.month
    df["Dia"] = df["DT_RETIRADA_RA"].dt.day
    df["AnoMes"] = df["DT_RETIRADA_RA"].dt.to_period("M")

    return df, alertas


def resumo(df):
    st.subheader("Resumo Geral")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total KM rodado", f"{df['KM_RODADO'].sum():,.0f} km".replace(",", ".").replace(".", ",", 1))
    with col2:
        st.metric("Receita Bruta", f"R$ {df['TOTAL_RA'].sum():,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
    with col3:
        extras = df['TX_RETORNO'].sum() + df['DESPESAS'].sum() + df['ADICIONAIS'].sum() + df['TX_SERVICO'].sum()
        st.metric("Custos Extras", f"R$ {extras:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))
    with col4:
        km_total = df['KM_RODADO'].sum()
        custo_total = df['TOTAL_RA'].sum()
        custo_medio = custo_total/km_total if km_total else 0
        st.metric("Custo médio/km", f"R$ {custo_medio:,.2f}".replace(",", "v").replace(".", ",").replace("v", "."))


def grafico_km(df, tipo_filtro):
    if tipo_filtro == "Resumo Mensal":
        st.subheader("Evolução de KM rodado por dia (Gráfico de barras)")
        dados_dia = df.groupby(df["DT_RETIRADA_RA"].dt.date)["KM_RODADO"].sum().reset_index()
        dados_dia.columns = ["Data", "KM_RODADO"]

        chart = alt.Chart(dados_dia).mark_bar().encode(
            x=alt.X("Data:T", title="Data"),
            y=alt.Y("KM_RODADO", title="KM Rodado"),
            tooltip=["Data", "KM_RODADO"]
        ).properties(width=700, height=400)
    else:
        st.subheader("Evolução de KM rodado por dia (Gráfico de linha)")
        dados_dia = df.groupby(df["DT_RETIRADA_RA"].dt.date)["KM_RODADO"].sum().reset_index()
        dados_dia.columns = ["Data", "KM_RODADO"]

        chart = alt.Chart(dados_dia).mark_line(point=True).encode(
            x=alt.X("Data:T", title="Data"),
            y=alt.Y("KM_RODADO", title="KM Rodado"),
            tooltip=["Data", "KM_RODADO"]
        ).properties(width=700, height=400)

    st.altair_chart(chart, use_container_width=True)


def subrelatorio_custos_extras(df):
    st.subheader("Sub-relatório: Custos Extras")
    colunas_extras = [
        "TOTAL_HORA_EXTRA", "QTDE_KM_EXTRA", "DESPESAS", "TX_RETORNO",
        "ADICIONAIS", "TX_SERVICO", "COMBUSTIVEL", "RECUPERACAO_AVARIAS", "REEMBOLSO"
    ]
    colunas_existentes = [col for col in colunas_extras if col in df.columns]
    if colunas_existentes:
        df_extras = df[colunas_existentes].copy()
        df_extras_sum = df_extras.sum().reset_index()
        df_extras_sum.columns = ["Categoria", "Total (R$)"]
        st.dataframe(df_extras_sum.style.format({"Total (R$)": lambda x: f"R$ {x:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")}))

        st.subheader("Distribuição dos Custos Extras")
        chart = alt.Chart(df_extras_sum).mark_arc(innerRadius=50).encode(
            theta="Total (R$):Q",
            color="Categoria:N",
            tooltip=["Categoria", "Total (R$)"]
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nenhuma das colunas de custos extras foi encontrada no relatório.")


def subrelatorio_por_usuario(df):
    st.subheader("Sub-relatório: Uso por Usuário (Preposto / Locatário)")
    if "PREPOSTO" in df.columns and "LOCATARIO" in df.columns:
        df["USUARIO"] = df["PREPOSTO"].fillna("").str.strip()
        df["USUARIO"] = df.apply(lambda row: row["LOCATARIO"] + " (Locatário)" if row["USUARIO"] == "" else row["USUARIO"], axis=1)

        colunas_custo = [
            "TX_RETORNO", "DESPESAS", "ADICIONAIS", "TX_SERVICO",
            "COMBUSTIVEL", "RECUPERACAO_AVARIAS", "REEMBOLSO"
        ]
        colunas_existentes = [col for col in colunas_custo if col in df.columns]

        agrupado = df.groupby("USUARIO")[["KM_RODADO"] + colunas_existentes].sum()
        agrupado["QTDE_RESERVAS"] = df.groupby("USUARIO")["KM_RODADO"].count()
        agrupado = agrupado.reset_index().sort_values(by="KM_RODADO", ascending=False)

        st.dataframe(agrupado.style.format({
            **{"KM_RODADO": "{:.0f} km", "QTDE_RESERVAS": "{:.0f}"},
            **{col: "R$ {:,.2f}" for col in colunas_existentes}
        }).format_index())

        st.subheader("Distribuição do KM rodado por Usuário")
        chart = alt.Chart(agrupado).mark_bar().encode(
            x=alt.X("KM_RODADO:Q", title="KM Rodado"),
            y=alt.Y("USUARIO:N", sort="-x", title="Usuário"),
            tooltip=["USUARIO", "KM_RODADO", "QTDE_RESERVAS"]
        ).properties(height=500)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("As colunas 'PREPOSTO' e 'LOCATARIO' não foram encontradas para esse sub-relatório.")

def subrelatorio_veiculos_por_mes(df):
    st.subheader("Sub-relatório: Quantidade de Usuários por Mês (Aparições)")

    # Criar coluna USUARIO igual ao usado no outro subrelatório
    if "PREPOSTO" in df.columns and "LOCATARIO" in df.columns:
        df["USUARIO"] = df["PREPOSTO"].fillna("").str.strip()
        df["USUARIO"] = df.apply(lambda row: row["LOCATARIO"] + " (Locatário)" if row["USUARIO"] == "" else row["USUARIO"], axis=1)
    else:
        st.warning("As colunas 'PREPOSTO' e 'LOCATARIO' não foram encontradas para este sub-relatório.")
        return

    # Contar aparições de usuários por AnoMes
    usuarios_mes = df.groupby("AnoMes")["USUARIO"].count().reset_index()
    usuarios_mes.columns = ["AnoMes", "Quantidade de Aparições"]

    st.dataframe(usuarios_mes)

    chart = alt.Chart(usuarios_mes).mark_bar().encode(
        x=alt.X("AnoMes:T", title="Mês"),
        y=alt.Y("Quantidade de Aparições:Q", title="Quantidade de Aparições do Usuário"),
        tooltip=["AnoMes", "Quantidade de Aparições"]
    ).properties(width=700, height=400)

    st.altair_chart(chart, use_container_width=True)


def subrelatorio_locacoes_por_usuario(df):
    st.subheader("Quantidade de Locações por Usuário no Período")

    if "PREPOSTO" in df.columns and "LOCATARIO" in df.columns:
        # Criar a coluna USUARIO igual nas outras funções
        df["USUARIO"] = df["PREPOSTO"].fillna("").str.strip()
        df["USUARIO"] = df.apply(lambda row: row["LOCATARIO"] + " (Locatário)" if row["USUARIO"] == "" else row["USUARIO"], axis=1)
    else:
        st.warning("As colunas 'PREPOSTO' e 'LOCATARIO' não foram encontradas para este relatório.")
        return

    # Contar quantas locações (linhas) por usuário no DataFrame filtrado
    locacoes_por_usuario = df.groupby("USUARIO").size().reset_index(name="Quantidade de Locações")

    # Ordenar do maior para menor
    locacoes_por_usuario = locacoes_por_usuario.sort_values(by="Quantidade de Locações", ascending=False)

    st.dataframe(locacoes_por_usuario)

    # Gráfico de barras: Usuário x Quantidade de Locações
    chart = alt.Chart(locacoes_por_usuario).mark_bar().encode(
        x=alt.X("Quantidade de Locações:Q", title="Quantidade de Locações"),
        y=alt.Y("USUARIO:N", sort="-x", title="Usuário"),
        tooltip=["USUARIO", "Quantidade de Locações"]
    ).properties(height=500)

    st.altair_chart(chart, use_container_width=True)



def main():
    st.title("Relatório de Custos - Aluguel de Veículos (Unidas)")

    uploaded_file = st.file_uploader("Faça upload do arquivo de relatório (.csv, .tsv, .xlsx)", type=["csv", "tsv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".xlsx"):
                df_raw = pd.read_excel(uploaded_file)
            elif uploaded_file.name.endswith(".tsv"):
                df_raw = pd.read_csv(uploaded_file, sep="\t")
            else:
                df_raw = pd.read_csv(uploaded_file, sep=None, engine='python')

            st.success("Arquivo carregado com sucesso!")
            st.write("Prévia dos dados:")
            st.dataframe(df_raw.head())

            df, alertas = preprocess(df_raw)

            st.sidebar.subheader("Filtros")
            opcoes_filtro = ["Selecionar Período", "Resumo Mensal"]
            escolha_filtro = st.sidebar.radio("Tipo de Filtro", opcoes_filtro)

            empresas_disponiveis = sorted(df["EMPRESA"].dropna().unique()) if "EMPRESA" in df.columns else []
            empresa_selecionada = st.sidebar.selectbox("Empresa", ["Todas"] + empresas_disponiveis) if empresas_disponiveis else "Todas"

            if escolha_filtro == "Selecionar Período":
                min_date = df["DT_RETIRADA_RA"].min()
                max_date = df["DT_RETIRADA_RA"].max()
                data_inicio = st.sidebar.date_input("Data Inicial", min_value=min_date.date(), max_value=max_date.date(), value=min_date.date())
                data_fim = st.sidebar.date_input("Data Final", min_value=min_date.date(), max_value=max_date.date(), value=max_date.date())
                df_periodo = df[(df["DT_RETIRADA_RA"] >= pd.to_datetime(data_inicio)) & (df["DT_RETIRADA_RA"] <= pd.to_datetime(data_fim))]
            else:
                anos_disponiveis = sorted(df["Ano"].dropna().unique())
                ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis)
                meses_disponiveis = sorted(df[df["Ano"] == ano_selecionado]["Mes"].dropna().unique())
                mes_selecionado = st.sidebar.selectbox("Mês", meses_disponiveis)
                df_periodo = df[(df["Ano"] == ano_selecionado) & (df["Mes"] == mes_selecionado)]

            if empresa_selecionada != "Todas":
                df_periodo = df_periodo[df_periodo["EMPRESA"] == empresa_selecionada]

            if alertas:
                with st.expander("⚠️ Alertas de conversão de dados"):
                    for alerta in alertas:
                        st.warning(alerta)

            resumo(df_periodo)

            if escolha_filtro == "Selecionar Período":
                st.write(f"### Dados de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')} ({len(df_periodo)} registros)")
            else:
                st.write(f"### Dados de {mes_selecionado:02d}/{ano_selecionado} ({len(df_periodo)} registros)")

            if empresa_selecionada != "Todas":
                st.write(f"### Empresa: {empresa_selecionada}")

            st.dataframe(df_periodo)

            grafico_km(df_periodo, escolha_filtro)
            subrelatorio_custos_extras(df_periodo)
            subrelatorio_por_usuario(df_periodo)
            subrelatorio_locacoes_por_usuario(df_periodo)

            st.download_button("Baixar dados filtrados", df_periodo.to_csv(index=False).encode("utf-8"), file_name="dados_filtrados.csv", mime="text/csv")

        except (pd.errors.ParserError, ValueError, KeyError, TypeError) as e:
            st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
