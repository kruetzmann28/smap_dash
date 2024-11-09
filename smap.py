import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config (page_title = 'SMAP')

# Título da aplicação
st.title("📱 SMAP")

# Texto de introdução
st.write("Bem-vindo ao aplicativo SMAP!")

# Caminhos para os arquivos Excel
smap_base = r'C:\Users\Fabiano\OneDrive - Telefonica\SMAP Acompanhamento\Versao indevido.xlsx'
base_colaboradores = r'C:\Users\Fabiano\OneDrive - Telefonica\Anatel\Anatel2.0\Colaboradores.xlsx'

try:
    # Leitura dos arquivos
    df_smap = pd.read_excel(smap_base)
    df_colaboradores = pd.read_excel(base_colaboradores)

    # Padronizando as colunas para o merge
    df_smap['USUARIO_CRIADOR'] = df_smap['USUARIO_CRIADOR'].str.upper().str.strip()
    df_colaboradores['COLABORADOR'] = df_colaboradores['COLABORADOR'].str.upper().str.strip()

    # Realizando o merge para adicionar a coluna `GERENTE` ao df_smap
    df_smap = pd.merge(
        df_smap,
        df_colaboradores[['COLABORADOR', 'GERENTE']], 
        left_on='USUARIO_CRIADOR', 
        right_on='COLABORADOR', 
        how='left'
    )

    # Remover a coluna `COLABORADOR` após o merge e renomear `USUARIO_CRIADOR` para `CRIADOR`
    df_smap = df_smap.drop(columns=['COLABORADOR']).rename(columns={'USUARIO_CRIADOR': 'CRIADOR'})

    # Converter 'DAT_ENTREGA' e 'DAT_RESOLUCAO' para datetime e manter registros com 'DAT_ENTREGA' válido
    df_smap['DAT_ENTREGA'] = pd.to_datetime(df_smap['DAT_ENTREGA'], errors='coerce')
    df_smap['DAT_RESOLUCAO'] = pd.to_datetime(df_smap['DAT_RESOLUCAO'], errors='coerce')
    df_smap = df_smap[df_smap['DAT_ENTREGA'].notna()]  # Mantém registros com 'DAT_ENTREGA' válido

    # Adicionar coluna de Ano e Mês para agrupamento
    df_smap['Ano_Mes'] = df_smap['DAT_ENTREGA'].dt.to_period('M')

    # Filtro de Gerente na barra lateral para múltiplas seleções
    gerentes = df_smap['GERENTE'].dropna().unique()
    gerentes_selecionados = st.sidebar.multiselect("Selecione um ou mais Gerentes:", options=gerentes)

    # Aplicar o filtro de gerente selecionado a todos os dados
    if gerentes_selecionados:
        df_filtrado = df_smap[df_smap['GERENTE'].isin(gerentes_selecionados)]
    else:
        df_filtrado = df_smap.copy()

    # Cálculo de indicadores mensais

    # Backlog: Contar os registros com 'DAT_RESOLUCAO' em branco, agrupados por mês
    backlog = df_filtrado[df_filtrado['DAT_RESOLUCAO'].isna()]
    backlog_mensal = backlog.groupby('Ano_Mes')['COD_EVENTO'].count()

    # Total backlog acumulado
    total_backlog = backlog['COD_EVENTO'].count()

    # Entrada total por mês (total de COD_EVENTO)
    entrada_mensal = df_filtrado.groupby('Ano_Mes')['COD_EVENTO'].count()

    # Dias úteis por mês
    unique_months = df_filtrado['Ano_Mes'].unique()
    dias_uteis_mensal = {str(month): np.busday_count(f"{month}-01", f"{month+1}-01") for month in unique_months}

    # Entrada por DU (total de entradas divididas pelos dias úteis de cada mês)
    entrada_por_du = entrada_mensal / entrada_mensal.index.to_series().apply(lambda x: dias_uteis_mensal[str(x)])

    # Total Indevidos e Share Indevidos
    total_indevidos = df_filtrado[df_filtrado['AÇÃO'] == 'INDEVIDO'].groupby('Ano_Mes')['COD_EVENTO'].count()
    share_indevidos = (total_indevidos / entrada_mensal * 100).fillna(0).round(1)

    # SLA: Dentro do prazo (<= 5 dias)
    df_filtrado['Dias_para_Resolucao'] = (df_filtrado['DAT_RESOLUCAO'] - df_filtrado['DAT_ENTREGA']).dt.days
    sla_mensal = (df_filtrado[df_filtrado['Dias_para_Resolucao'] <= 5].groupby('Ano_Mes')['COD_EVENTO'].count() / entrada_mensal * 100).fillna(0).round(1)

    # Definir o último mês da base de dados como o mês vigente
    ultimo_mes = df_filtrado['Ano_Mes'].max()

    # Calcular os valores dos principais indicadores para o último mês
    sla_vigente = sla_mensal.get(ultimo_mes, 0)  # SLA para o último mês
    backlog_vigente = backlog_mensal.get(ultimo_mes, 0)  # Backlog para o último mês
    share_indevidos_vigente = share_indevidos.get(ultimo_mes, 0)  # Share Indevidos para o último mês

    # Reincidência: Verificar chamadas reincidentes para o mesmo motivo no mesmo mês
    df_filtrado['reincidencia'] = df_filtrado.groupby(['Ano_Mes', 'DES_NUM_CLIENTE', 'DES_TIPO_RECLAMACAO'])['COD_EVENTO']\
        .transform('size') > 1

    # Exibir os principais indicadores em três colunas
    col1, col2, col3 = st.columns(3)
    col1.metric("SLA (%)", f"{sla_vigente:.2f}%")
    col2.metric("Backlog Total", total_backlog)
    col3.metric("Share Indevidos (%)", f"{share_indevidos_vigente:.2f}%")

    # Combinar os indicadores em um DataFrame para exibição detalhada
    indicadores = pd.DataFrame({
        'Entrada': entrada_mensal,
        'Entrada DU': entrada_por_du.round(1),
        'Share Indevidos (%)': share_indevidos,
        'Total Indevidos': total_indevidos.fillna(0).astype(int),
        'SLA (%)': sla_mensal,
        'Backlog': backlog_mensal,
        'Reincidência (%)': (df_filtrado['reincidencia'].groupby(df_filtrado['Ano_Mes']).mean() * 100).round(1)
    }).fillna(0).T  # Transpor para exibir meses como colunas

    # Exibir a tabela de indicadores
    st.write("Indicadores Mensais")
    st.dataframe(indicadores)

    # Gráficos e exibição de dados seguem... # Gráficos
    chamados_por_mes = df_filtrado.groupby(['Ano_Mes']).size().reset_index(name='Volume_Chamados')
    chamados_por_mes['Ano_Mes'] = chamados_por_mes['Ano_Mes'].astype(str)
    fig_colunas = px.bar(
        chamados_por_mes,
        x='Ano_Mes',
        y='Volume_Chamados',
        labels={'Ano_Mes': 'Mês', 'Volume_Chamados': 'Volume de Chamados'},
        title='Volume de Chamados por Mês - Gerentes Selecionados',
        text='Volume_Chamados'
    )
    fig_colunas.update_traces(marker_color='purple', textposition='inside')
    fig_colunas.update_layout(font=dict(family="Arial", size=14, color="black"))
    st.plotly_chart(fig_colunas, use_container_width=True)

    # Gráfico de linha para percentual de Indevidos
    indevido_percentual = (
        df_filtrado.groupby('Ano_Mes')
        .apply(lambda x: pd.Series({
            'Volume_Indevido': (x['AÇÃO'] == 'INDEVIDO').sum(),
            'Percentual_Indevido': (x['AÇÃO'] == 'INDEVIDO').sum() / len(x) * 100
        }))
        .reset_index()
    )
    indevido_percentual['Ano_Mes'] = indevido_percentual['Ano_Mes'].astype(str)
    fig_linha = go.Figure()
    fig_linha.add_trace(go.Scatter(
        x=indevido_percentual['Ano_Mes'],
        y=indevido_percentual['Percentual_Indevido'],
        mode='lines+text',
        text=indevido_percentual['Percentual_Indevido'].round(2).astype(str) + '%',
        textposition="top right",
        line=dict(color='darkblue', width=2),
        name='Percentual de Indevidos (%)'
    ))
    fig_linha.update_layout(
        title='Percentual de Indevidos ao Longo do Tempo',
        xaxis_title='Mês',
        yaxis_title='Percentual de Indevidos (%)',
        font=dict(family="Arial", size=10, color="black"),
        margin=dict(l=40, r=40, t=60, b=40)
    )
    st.plotly_chart(fig_linha, use_container_width=True)

    # Adicionar colunas para Dias_para_Resolucao e SLA_Status
    df_filtrado['Dias_para_Resolucao'] = (df_filtrado['DAT_RESOLUCAO'] - df_filtrado['DAT_ENTREGA']).dt.days

        # Adicionar coluna para indicar se o chamado está "Dentro do Prazo" ou "Fora do Prazo"
    df_filtrado['SLA_Status'] = df_filtrado['Dias_para_Resolucao'].apply(lambda x: 'Dentro do Prazo' if x <= 5 else 'Fora do Prazo')

    # Adicionar uma coluna 'reincidencia' diretamente no df_filtrado
# Agrupamos e marcamos como True para clientes que aparecem mais de uma vez no mesmo mês e motivo
    df_filtrado['reincidencia'] = df_filtrado.groupby(['Ano_Mes', 'DES_NUM_CLIENTE', 'DES_TIPO_RECLAMACAO'])['COD_EVENTO']\
    .transform('size') > 1

# Exibir o DataFrame com a nova coluna 'reincidencia' no Streamlit
    st.write("Dados do SMAP filtrado com SLA e Reincidência")
    st.dataframe(df_filtrado[[
    'DAT_ENTREGA', 'DAT_RESOLUCAO', 'Dias_para_Resolucao', 'SLA_Status', 
    'GERENTE', 'CRIADOR', 'COD_EVENTO', 'DES_ACAO_EVENTO', 
    'DES_TIPO_RECLAMACAO', 'DES_DETALHE_RECLAMACAO', 'DES_SUBDETALHE_RECLAMACAO', 
    'DES_NUM_CLIENTE', 'reincidencia'
]])




except Exception as e:
    st.error(f"Erro ao carregar ou combinar os arquivos: {e}")

    






















