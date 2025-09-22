import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd
import numpy as np
import base64
from io import BytesIO
import json
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---

st.set_page_config(
    page_title="Análise Interativa de Votação - Município do Rio de Janeiro",
    page_icon="📈",
    layout="wide",
)

st.title("Análise Interativa de Votação - Município do Rio de Janeiro")

# --- FUNÇÕES AUXILIARES ---
def create_download_link(data, filename, file_type):
    """Cria link de download para arquivos"""
    if file_type == "json":
        b64 = base64.b64encode(data.encode()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="{filename}">Baixar {filename}</a>'
    elif file_type == "csv":
        b64 = base64.b64encode(data.encode()).decode()
        href = f'<a href="data:text/csv;base64,{b64}" download="{filename}">Baixar {filename}</a>'
    return href

def export_map_data(df, tipo_visualizacao, candidato_selecionado):
    """Exporta dados do mapa para diferentes formatos"""
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    
    # Preparar dados para exportação
    export_data = df.copy()
    
    # Adicionar informações de contexto
    export_data['Tipo_Visualizacao'] = tipo_visualizacao
    export_data['Candidato'] = candidato_selecionado if candidato_selecionado != "Visão Geral" else "Ambos"
    export_data['Data_Exportacao'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return export_data, timestamp

def criar_ranking_sinergia(df_bairros, tipo_mancha):
    """Cria ranking de sinergia por bairro"""
    if df_bairros.empty:
        return None, None
    
    # Prepara dados para ranking
    ranking_data = df_bairros[['nome', 'Sinergia', 'Forca_Conjunta', 'Total_Votos', NOME_FERNANDO, NOME_INDIA]].copy()
    ranking_data = ranking_data[ranking_data['Total_Votos'] > 0]  # Remove bairros sem votos
    
    if ranking_data.empty:
        return None, None
    
    # Define coluna para ranking baseado no tipo
    coluna_ranking = 'Sinergia' if tipo_mancha == 'Apenas Sinergia' else 'Forca_Conjunta'
    
    # Top 5 maior
    top_5_maior = ranking_data.nlargest(5, coluna_ranking)
    
    # Top 5 menor
    top_5_menor = ranking_data.nsmallest(5, coluna_ranking)
    
    return top_5_maior, top_5_menor

# --- CONSTANTES ---
COLUNA_CANDIDATO = 'NM_VOTAVEL'
NOME_FERNANDO = 'FERNANDO CESAR CAMPOS PAES'
NOME_INDIA = 'AMANDA BRANDAO ARMELAU'
URL_GEOJSON_ESTADO_RIO = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-33-mun.json"
URL_GEOJSON_BAIRROS_RIO = "https://pgeo3.rio.rj.gov.br/arcgis/rest/services/Cartografia/Limites_administrativos/MapServer/4/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
COR_FERNANDO = "#1E90FF"  # Azul
COR_INDIA = "#FF0000"     # Vermelho
RGB_FERNANDO = [30, 144, 255]
RGB_INDIA = [255, 0, 0]


# --- FUNÇÕES AUXILIARES ---
# --- FUNÇÕES AUXILIARES ---
@st.cache_data
def carregar_dados():
    """
    Carrega e pré-processa os dados de votação e os geojsons do município e bairros do Rio de Janeiro.
    A função também corrige erros de formatação nas coordenadas e associa cada local de votação a um bairro.
    """
    def corrigir_coordenada(coord):
        s = str(coord).replace(',', '.').strip()
        try:
            return float(s)
        except ValueError:
            is_neg = s.startswith('-')
            digits = ''.join(filter(str.isdigit, s))
            if not digits: return None
            # Ajuste para diferentes formatos de coordenadas sem ponto decimal
            s_clean = f"{'-' if is_neg else ''}{s.replace('-', '').replace('.', '')}"
            if len(s_clean) > 8: # Provavelmente formato com muitos decimais
                 s_clean = f"{s_clean[:3]}.{s_clean[3:]}"
            else:
                 s_clean = f"{s_clean[:2]}.{s_clean[2:]}"
            return pd.to_numeric(s_clean, errors='coerce')


    df = pd.read_csv('votacao_com_coordenadas.csv', sep=';', encoding='utf-8-sig', on_bad_lines='skip')
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    df.columns = [col.strip() for col in df.columns]

    df['LATITUDE'] = df['LATITUDE'].apply(corrigir_coordenada)
    df['LONGITUDE'] = df['LONGITUDE'].apply(corrigir_coordenada)
    df.dropna(subset=['LATITUDE', 'LONGITUDE'], inplace=True)
    df.rename(columns={'LATITUDE': 'lat', 'LONGITUDE': 'lon'}, inplace=True)

    gdf_bairros = gpd.read_file(URL_GEOJSON_BAIRROS_RIO)
    gdf_votacao = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326"
    )
    gdf_bairros = gdf_bairros.to_crs(gdf_votacao.crs)
    gdf_merged = gpd.sjoin(gdf_votacao, gdf_bairros, how="left", predicate='intersects')
    
    df_com_bairro = pd.DataFrame(gdf_merged.drop(columns=['geometry', 'index_right']))
    df_com_bairro.rename(columns={'nome': 'NOME_BAIRRO'}, inplace=True)
    
    # --- LINHA DE CÓDIGO ADICIONADA PARA A CORREÇÃO ---
    # Preenche os bairros não encontrados com um valor padrão para evitar que sejam descartados.
    # df_com_bairro['NOME_BAIRRO'].fillna('Bairro não identificado', inplace=True)
    # --- FIM DA CORREÇÃO ---

    gdf_estado = gpd.read_file(URL_GEOJSON_ESTADO_RIO)
    gdf_municipio = gdf_estado[gdf_estado['name'] == 'Rio de Janeiro']
    return df_com_bairro, gdf_municipio, gdf_bairros

# --- CARREGAMENTO DOS DADOS ---
df_original, municipio_rj_geo, bairros_rj_geo = carregar_dados()


# --- EXIBIÇÃO DOS TOTAIS DE VOTOS ---
votos_fernando = int(df_original[df_original[COLUNA_CANDIDATO] == NOME_FERNANDO]['QT_VOTOS_TOTAL'].sum())
votos_india = int(df_original[df_original[COLUNA_CANDIDATO] == NOME_INDIA]['QT_VOTOS_TOTAL'].sum())

# **CORREÇÃO APLICADA AQUI**
# Formata o número com ponto como separador de milhar antes de exibi-lo.
formatted_votos_fernando = f"{votos_fernando:,}".replace(",", ".")
formatted_votos_india = f"{votos_india:,}".replace(",", ".")

# Estilo CSS para os cartões de métrica
st.markdown("""
<style>
/* Estilo para garantir que o contêiner da métrica não adicione margens extras indesejadas */
div[data-testid="stMetric"] > div {
    margin: 0 !important;
    padding: 0 !important;
}
.metric-container {
    background-color: transparent;
    border: none;
    border-radius: 0.5rem;
    padding: 1rem;
    margin-bottom: 1rem;
}
.metric-label {
    font-size: 0.9em;
    color: #666666;
    opacity: 1;
}
.metric-value {
    font-size: 1.75rem;
    font-weight: 600;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

col1, col2, _ = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">Total de Votos - {NOME_FERNANDO}</div>
        <div class="metric-value" style="color: {COR_FERNANDO};">{formatted_votos_fernando}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">Total de Votos - {NOME_INDIA}</div>
        <div class="metric-value" style="color: {COR_INDIA};">{formatted_votos_india}</div>
    </div>
    """, unsafe_allow_html=True)
st.divider()

# --- FILTROS NA PÁGINA PRINCIPAL ---
st.subheader("Filtros de Visualização")
filt_col1, filt_col2, filt_col3 = st.columns([1, 1, 2])

with filt_col1:
    # **ALTERAÇÃO AQUI: Removido o modo "Comparativo"**
    modo_analise = st.radio(
        "Modo de Análise:",
        ("Visão Geral", "Apenas Fernando Paes", "Apenas Índia Armelau"),
        index=0
    )

df_pre_filtro = df_original.copy()
if modo_analise == "Apenas Fernando Paes":
    df_pre_filtro = df_original[df_original[COLUNA_CANDIDATO] == NOME_FERNANDO]
elif modo_analise == "Apenas Índia Armelau":
    df_pre_filtro = df_original[df_original[COLUNA_CANDIDATO] == NOME_INDIA]


with filt_col2:
    zonas_disponiveis = sorted(df_pre_filtro['NR_ZONA'].unique())
    zona_selecionada = st.selectbox("Filtrar por Zona Eleitoral:", options=['Todas'] + zonas_disponiveis)

df_filtrado = df_pre_filtro.copy()
if zona_selecionada != 'Todas':
    df_filtrado = df_pre_filtro[df_pre_filtro['NR_ZONA'] == zona_selecionada]

with filt_col3:
    locais_disponiveis = sorted(df_filtrado['NM_LOCAL_VOTACAO'].unique())
    locais_selecionados = st.multiselect("Pesquisar por Local de Votação:", options=locais_disponiveis, placeholder="Digite o nome de um local...")

if locais_selecionados:
    df_filtrado = df_filtrado[df_filtrado['NM_LOCAL_VOTACAO'].isin(locais_selecionados)]

st.divider()

# --- PRÉ-CÁLCULO DOS DADOS PARA O MAPA DE PONTOS ---
df_mapa = pd.DataFrame()
if not df_filtrado.empty and 'NOME_BAIRRO' in df_filtrado.columns:
    if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
        df_mapa = df_filtrado[['NM_LOCAL_VOTACAO', 'lat', 'lon', 'QT_VOTOS_TOTAL']].copy()
        df_mapa.rename(columns={'QT_VOTOS_TOTAL': 'Votos_Candidato_Unico'}, inplace=True)
    else: # modo_analise == "Visão Geral"
        df_mapa = df_filtrado.pivot_table(index=['NM_LOCAL_VOTACAO', 'lat', 'lon'], columns=COLUNA_CANDIDATO, values='QT_VOTOS_TOTAL', aggfunc='sum').reset_index().fillna(0)
        if NOME_FERNANDO not in df_mapa: df_mapa[NOME_FERNANDO] = 0
        if NOME_INDIA not in df_mapa: df_mapa[NOME_INDIA] = 0
        df_mapa[NOME_FERNANDO] = df_mapa[NOME_FERNANDO].astype(int)
        df_mapa[NOME_INDIA] = df_mapa[NOME_INDIA].astype(int)
        df_mapa['Diferença'] = df_mapa[NOME_FERNANDO] - df_mapa[NOME_INDIA]
        df_mapa['Total_Votos'] = df_mapa[NOME_FERNANDO] + df_mapa[NOME_INDIA]
        df_mapa['Diferenca_Absoluta'] = df_mapa['Diferença'].abs()
        epsilon = 1e-9
        proporcao_diferenca = df_mapa['Diferenca_Absoluta'] / (df_mapa['Total_Votos'] + epsilon)
        fator_sinergia = 1 - proporcao_diferenca
        fator_sinergia_ajustado = fator_sinergia ** 0.5
        df_mapa['Sinergia_Peso'] = df_mapa['Total_Votos'] * fator_sinergia_ajustado

# --- MAPA E LEGENDA INTERATIVA ---
map_col, legend_col = st.columns([4, 1])

with legend_col:
    st.header("Legenda do Mapa")
    tipo_visualizacao = st.radio(
        "Tipo de Visualização:",
        ("Pontos", "Mancha de Votos"),
        index=1,
        help="'Pontos': vencedor por local. 'Mancha de Votos': sinergia eleitoral entre candidatos."
    )
    st.divider()

    if tipo_visualizacao == "Pontos" and not df_mapa.empty:
        if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
            candidato_selecionado = "Fernando Paes" if modo_analise == "Apenas Fernando Paes" else "Índia Armelau"
            cor_base_html = COR_FERNANDO if candidato_selecionado == "Fernando Paes" else COR_INDIA
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {cor_base_html}; border-radius: 50%; margin-right: 10px;"></div><span>{candidato_selecionado}</span></div>', unsafe_allow_html=True)
        else:
            modo_cor = st.radio("Colorir pontos por:", ("Sinergia (Relativa %)", "Sinergia (Absoluta)", "Magnitude da Vitória", "Volume de Votos (Ponderado)"))
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {COR_FERNANDO}; border-radius: 50%; margin-right: 10px;"></div><span>Fernando Paes</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 15px;"><div style="width: 20px; height: 20px; background-color: {COR_INDIA}; border-radius: 50%; margin-right: 10px;"></div><span>Índia Armelau</span></div>', unsafe_allow_html=True)

    elif tipo_visualizacao == "Mancha de Votos":
        if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
            candidato_selecionado = "Fernando Paes" if modo_analise == "Apenas Fernando Paes" else "Índia Armelau"
            cor_base_html = COR_FERNANDO if candidato_selecionado == "Fernando Paes" else COR_INDIA
            st.markdown(f"**Mancha de Votos - {candidato_selecionado}**")
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {cor_base_html}; border-radius: 5px; margin-right: 10px;"></div><span>Força Eleitoral</span></div>', unsafe_allow_html=True)
            st.markdown("**Escala de Intensidade:**<p style='font-size: 0.9em;'>Cada bairro é colorido conforme a <b>força eleitoral</b> do candidato. Quanto mais <b>intensa</b> a cor, <b>maior</b> o número de votos na região.</p>", unsafe_allow_html=True)
        else:
            st.markdown("**Mancha de Sinergia - Parceria Eleitoral**")
            
            # Opção para escolher entre Força Conjunta e Apenas Sinergia
            tipo_mancha = st.radio(
                "Visualizar por:",
                ("Força Conjunta", "Apenas Sinergia"),
                help="'Força Conjunta': combina sinergia + volume total. 'Apenas Sinergia': foca na transferência de votos."
            )
            
            if tipo_mancha == "Força Conjunta":
                st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: #1E90FF; border-radius: 5px; margin-right: 10px;"></div><span>Força da Parceria</span></div>', unsafe_allow_html=True)
                st.markdown("**Escala de Intensidade:**<p style='font-size: 0.9em;'>Escala de <b>azul</b> com intensidades diferentes. Quanto mais <b>intenso</b> o azul, maior a <b>força conjunta</b> (sinergia + volume de votos) entre Fernando Paes e Índia Armelau.</p>", unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: #1E90FF; border-radius: 5px; margin-right: 10px;"></div><span>Transferência de Votos</span></div>', unsafe_allow_html=True)
                st.markdown("**Escala de Sinergia:**<p style='font-size: 0.9em;'>Escala de <b>azul</b> focada na <b>transferência de votos</b> entre os candidatos. Quanto mais <b>intenso</b> o azul, maior a <b>sinergia eleitoral</b> na região, independente do volume total.</p>", unsafe_allow_html=True)

# --- RENDERIZAÇÃO DO MAPA ---
with map_col:
    view_state = pdk.ViewState(latitude=-22.9068, longitude=-43.1729, zoom=9.5, pitch=0)
    polygon_layer = pdk.Layer("GeoJsonLayer", data=municipio_rj_geo, get_fill_color="[220, 220, 220, 40]", get_line_color="[0, 0, 0, 100]", get_line_width=30)

    if not df_filtrado.empty and 'NOME_BAIRRO' in df_filtrado.columns:
        if tipo_visualizacao == "Pontos":
            if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
                max_votos_unico = df_mapa['Votos_Candidato_Unico'].max() or 1
                cor_base_rgb = RGB_FERNANDO if modo_analise == "Apenas Fernando Paes" else RGB_INDIA
                df_mapa['cor'] = df_mapa['Votos_Candidato_Unico'].apply(lambda x: cor_base_rgb + [int(50 + (x / max_votos_unico) * 205)])
                df_mapa['raio'] = df_mapa['Votos_Candidato_Unico'].apply(lambda x: 100 + (x / max_votos_unico * 400))
                df_mapa['tooltip'] = df_mapa.apply(lambda r: f"<b>{r['NM_LOCAL_VOTACAO']}</b><br>Votos: {r['Votos_Candidato_Unico']}", axis=1)
            else: # modo_analise == "Visão Geral"
                max_abs_diff = df_mapa['Diferença'].abs().max() or 1
                max_total_votos = df_mapa['Total_Votos'].max() or 1
                df_mapa['Diff_Relativa'] = (df_mapa['Diferença'].abs() / (df_mapa['Total_Votos'] + 1e-9)).fillna(0)
                def get_color(row, mode):
                    diff, total, diff_rel = row['Diferença'], row['Total_Votos'], row['Diff_Relativa']
                    base_color = RGB_FERNANDO if diff > 0 else (RGB_INDIA if diff < 0 else [128, 128, 128])
                    alpha = 128
                    if mode == "Sinergia (Relativa %)": alpha = int(100 + (1 - diff_rel) * 155)
                    elif mode == "Sinergia (Absoluta)": alpha = int(100 + (1 - (abs(diff) / max_abs_diff)) * 155) if max_abs_diff > 0 else 100
                    elif mode == "Magnitude da Vitória": alpha = int(100 + (abs(diff) / max_abs_diff) * 155) if max_abs_diff > 0 else 100
                    elif mode == "Volume de Votos (Ponderado)": base_color, alpha = [0, 0, 255], int(50 + (total / max_total_votos) * 205) if max_total_votos > 0 else 50
                    return base_color + [alpha]
                df_mapa['cor'] = df_mapa.apply(lambda row: get_color(row, modo_cor), axis=1)
                df_mapa['raio'] = df_mapa['Total_Votos'].apply(lambda x: 100 + (x / max_total_votos * 400) if max_total_votos > 0 else 100)
                df_mapa['tooltip'] = df_mapa.apply(lambda r: f"<b>{r['NM_LOCAL_VOTACAO']}</b><br>F. Paes: {r[NOME_FERNANDO]}<br>Í. Armelau: {r[NOME_INDIA]}<br><b>Diferença: {r['Diferença']}</b><br>Total: {r['Total_Votos']}", axis=1)

            scatterplot_layer = pdk.Layer("ScatterplotLayer", data=df_mapa, get_position='[lon, lat]', get_color='cor', get_radius='raio', pickable=True)
            st.pydeck_chart(pdk.Deck(layers=[polygon_layer, scatterplot_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "{tooltip}"}))

            # Botões de exportação
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Exportar Dados (CSV)", key="export_csv_pontos"):
                    export_data, timestamp = export_map_data(df_mapa, "Pontos", modo_analise)
                    csv_data = export_data.to_csv(index=False, encoding='utf-8-sig')
                    st.markdown(create_download_link(csv_data, f"dados_pontos_{timestamp}.csv", "csv"), unsafe_allow_html=True)
            
            with col2:
                if st.button("Exportar Dados (JSON)", key="export_json_pontos"):
                    export_data, timestamp = export_map_data(df_mapa, "Pontos", modo_analise)
                    json_data = export_data.to_json(orient='records', force_ascii=False, indent=2)
                    st.markdown(create_download_link(json_data, f"dados_pontos_{timestamp}.json", "json"), unsafe_allow_html=True)
            
            with col3:
                if st.button("Salvar como PDF", key="export_pdf_pontos"):
                    st.info("Use Ctrl+P no navegador para salvar o mapa como PDF")

        elif tipo_visualizacao == "Mancha de Votos":
            # Layout com mapa e ranking lado a lado
            col_mapa, col_ranking = st.columns([2, 1])
            
            with col_mapa:
                if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
                    # Para candidato individual, mostra força eleitoral
                    candidato_selecionado = NOME_FERNANDO if modo_analise == "Apenas Fernando Paes" else NOME_INDIA
                    cor_base_rgb = RGB_FERNANDO if modo_analise == "Apenas Fernando Paes" else RGB_INDIA
                
                    # Agrupa votos por bairro
                    df_bairros_mancha = df_filtrado.groupby('NOME_BAIRRO')['QT_VOTOS_TOTAL'].sum().reset_index()
                    gdf_bairros_mancha = bairros_rj_geo.merge(df_bairros_mancha, left_on='nome', right_on='NOME_BAIRRO', how='left').fillna(0)
                
                    # Calcula intensidade da mancha (0 a 1)
                    max_votos = gdf_bairros_mancha['QT_VOTOS_TOTAL'].max() or 1
                    gdf_bairros_mancha['intensidade'] = gdf_bairros_mancha['QT_VOTOS_TOTAL'] / max_votos
                    
                    # Cria cor baseada na intensidade
                    def get_mancha_color_unico(intensidade):
                        alpha = int(50 + intensidade * 205)  # Transparência baseada na intensidade
                        return cor_base_rgb + [alpha]
                    
                    gdf_bairros_mancha['cor'] = gdf_bairros_mancha['intensidade'].apply(get_mancha_color_unico)
                    gdf_bairros_mancha['tooltip'] = gdf_bairros_mancha.apply(
                        lambda r: f"<b>Bairro: {r['nome']}</b><br>"
                                f"Votos: {int(r['QT_VOTOS_TOTAL'])}<br>"
                                f"Força Eleitoral: {r['intensidade']:.1%}", axis=1)
                    
                    mancha_layer = pdk.Layer(
                        "GeoJsonLayer", data=gdf_bairros_mancha, opacity=0.8, pickable=True,
                        get_fill_color='cor', get_line_color=[0, 0, 0, 100], get_line_width=15,
                    )
                    st.pydeck_chart(pdk.Deck(layers=[polygon_layer, mancha_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "{tooltip}"}))
                
                    # Botões de exportação para candidato individual
                    if st.button("Exportar Dados (CSV)", key="export_csv_mancha_individual"):
                        export_data, timestamp = export_map_data(gdf_bairros_mancha, "Mancha de Votos", modo_analise)
                        csv_data = export_data.to_csv(index=False, encoding='utf-8-sig')
                        st.markdown(create_download_link(csv_data, f"dados_mancha_{timestamp}.csv", "csv"), unsafe_allow_html=True)
                    
                    if st.button("Exportar Dados (JSON)", key="export_json_mancha_individual"):
                        export_data, timestamp = export_map_data(gdf_bairros_mancha, "Mancha de Votos", modo_analise)
                        json_data = export_data.to_json(orient='records', force_ascii=False, indent=2)
                        st.markdown(create_download_link(json_data, f"dados_mancha_{timestamp}.json", "json"), unsafe_allow_html=True)
                    
                    if st.button("Salvar como PDF", key="export_pdf_mancha_individual"):
                        st.info("Use Ctrl+P no navegador para salvar o mapa como PDF")
                    
                    if st.button("Capturar Mapa", key="screenshot_mancha_individual"):
                        st.info("Use a ferramenta de captura de tela do navegador (F12 > Screenshot) para capturar o mapa em alta qualidade")
                
                else: # modo_analise == "Visão Geral" - MANCHA DE SINERGIA
                    # Agrupa votos por bairro para cada candidato
                    df_bairros_mancha = df_filtrado.pivot_table(index='NOME_BAIRRO', columns=COLUNA_CANDIDATO, values='QT_VOTOS_TOTAL', aggfunc='sum').fillna(0)
                    if NOME_FERNANDO not in df_bairros_mancha: df_bairros_mancha[NOME_FERNANDO] = 0
                    if NOME_INDIA not in df_bairros_mancha: df_bairros_mancha[NOME_INDIA] = 0
                    
                    # Calcula SINERGIA - força conjunta dos candidatos
                    df_bairros_mancha['Total_Votos'] = df_bairros_mancha[NOME_FERNANDO] + df_bairros_mancha[NOME_INDIA]
                    df_bairros_mancha['Diferenca_Absoluta'] = abs(df_bairros_mancha[NOME_FERNANDO] - df_bairros_mancha[NOME_INDIA])
                
                    # SINERGIA: quanto mais equilibrados os votos, maior a sinergia
                    # Sinergia = 1 - (diferença absoluta / total de votos)
                    epsilon = 1e-9
                    df_bairros_mancha['Sinergia'] = 1 - (df_bairros_mancha['Diferenca_Absoluta'] / (df_bairros_mancha['Total_Votos'] + epsilon))
                
                    # Calcula força conjunta (sinergia + volume)
                    max_total = df_bairros_mancha['Total_Votos'].max() or 1
                    df_bairros_mancha['Forca_Conjunta'] = df_bairros_mancha['Sinergia'] * (df_bairros_mancha['Total_Votos'] / max_total)
                
                    # Define qual valor usar baseado na opção selecionada
                    if tipo_mancha == "Apenas Sinergia":
                        df_bairros_mancha['Valor_Visualizacao'] = df_bairros_mancha['Sinergia']
                    else:  # Força Conjunta
                        df_bairros_mancha['Valor_Visualizacao'] = df_bairros_mancha['Forca_Conjunta']
                    
                    gdf_bairros_mancha = bairros_rj_geo.merge(df_bairros_mancha, left_on='nome', right_index=True, how='left').fillna(0)
                
                    # Calcula percentis dos dados reais para criar escala baseada na distribuição
                    valores_para_escala = df_bairros_mancha['Valor_Visualizacao'].values
                    valores_para_escala = valores_para_escala[valores_para_escala > 0]  # Remove zeros
                    
                    if len(valores_para_escala) > 0:
                        # Calcula percentis para criar escala baseada na distribuição real
                        p25 = np.percentile(valores_para_escala, 25)
                        p50 = np.percentile(valores_para_escala, 50)
                        p75 = np.percentile(valores_para_escala, 75)
                        p90 = np.percentile(valores_para_escala, 90)
                        p95 = np.percentile(valores_para_escala, 95)
                        p99 = np.percentile(valores_para_escala, 99)
                    else:
                        p25 = p50 = p75 = p90 = p95 = p99 = 0.01
                
                
                    # Cria cor com ESCALA EXPONENCIAL - SEPARAÇÃO MÁXIMA DOS VALORES ALTOS
                    def get_mancha_color_sinergia(row):
                        valor_base = row['Valor_Visualizacao']
                        
                        # ESCALA EXPONENCIAL PARA SEPARAR MELHOR OS VALORES ALTOS
                        if valor_base <= 0:
                            return [200, 200, 200, 5]  # Cinza quase invisível
                        elif valor_base <= p25:
                            return [30, 144, 255, 10]  # Azul MUITO claro
                        elif valor_base <= p50:
                            return [30, 144, 255, 25]  # Azul claro
                        elif valor_base <= p75:
                            return [30, 144, 255, 50]  # Azul médio
                        elif valor_base <= p90:
                            return [30, 144, 255, 100]  # Azul forte
                        elif valor_base <= p95:
                            return [30, 144, 255, 160]  # Azul muito forte
                        elif valor_base <= p99:
                            return [30, 144, 255, 200]  # Azul intenso
                        else:
                            return [30, 144, 255, 255]  # Azul máximo
                
                    gdf_bairros_mancha['cor'] = gdf_bairros_mancha.apply(get_mancha_color_sinergia, axis=1)
                    gdf_bairros_mancha['tooltip'] = gdf_bairros_mancha.apply(
                        lambda r: f"<b>Bairro: {r['nome']}</b><br>"
                                f"F. Paes: {int(r[NOME_FERNANDO])}<br>"
                                f"Í. Armelau: {int(r[NOME_INDIA])}<br>"
                                f"<b>Total: {int(r['Total_Votos'])}</b><br>"
                                f"<b>Sinergia: {r['Sinergia']:.1%}</b><br>"
                                f"Força Conjunta: {r['Forca_Conjunta']:.1%}<br>"
                                f"<b>{tipo_mancha}: {r['Valor_Visualizacao']:.1%}</b>", axis=1)
                    
                    mancha_layer = pdk.Layer(
                        "GeoJsonLayer", data=gdf_bairros_mancha, opacity=0.8, pickable=True,
                        get_fill_color='cor', get_line_color=[0, 0, 0, 100], get_line_width=15,
                    )
                    st.pydeck_chart(pdk.Deck(layers=[polygon_layer, mancha_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "{tooltip}"}))
                
                    # Botões de exportação para sinergia
                    if st.button("Exportar Dados (CSV)", key="export_csv_sinergia"):
                        export_data, timestamp = export_map_data(gdf_bairros_mancha, f"Mancha de Sinergia - {tipo_mancha}", "Visão Geral")
                        csv_data = export_data.to_csv(index=False, encoding='utf-8-sig')
                        st.markdown(create_download_link(csv_data, f"dados_sinergia_{timestamp}.csv", "csv"), unsafe_allow_html=True)
                    
                    if st.button("Exportar Dados (JSON)", key="export_json_sinergia"):
                        export_data, timestamp = export_map_data(gdf_bairros_mancha, f"Mancha de Sinergia - {tipo_mancha}", "Visão Geral")
                        json_data = export_data.to_json(orient='records', force_ascii=False, indent=2)
                        st.markdown(create_download_link(json_data, f"dados_sinergia_{timestamp}.json", "json"), unsafe_allow_html=True)
                    
                    if st.button("Salvar como PDF", key="export_pdf_sinergia"):
                        st.info("Use Ctrl+P no navegador para salvar o mapa como PDF")
                    
                    if st.button("Capturar Mapa", key="screenshot_sinergia"):
                        st.info("Use a ferramenta de captura de tela do navegador (F12 > Screenshot) para capturar o mapa em alta qualidade")
            
            # Seção de ranking ao lado do mapa
            with col_ranking:
                st.subheader("Ranking de Sinergia")
                
                # Cria ranking baseado na seleção atual
                top_5_maior, top_5_menor = criar_ranking_sinergia(gdf_bairros_mancha, tipo_mancha)
                
                if top_5_maior is not None and not top_5_maior.empty:
                    # Top 5 Maior Sinergia
                    st.markdown("**Top 5 Maior Sinergia**")
                    for i, (_, row) in enumerate(top_5_maior.iterrows(), 1):
                        coluna_ranking = 'Sinergia' if tipo_mancha == 'Apenas Sinergia' else 'Forca_Conjunta'
                        valor = row[coluna_ranking]
                        st.markdown(f"**{i}.** {row['nome']}<br><small>{valor:.1%}</small>", unsafe_allow_html=True)
                    
                    st.divider()
                    
                    # Top 5 Menor Sinergia
                    st.markdown("**Top 5 Menor Sinergia**")
                    for i, (_, row) in enumerate(top_5_menor.iterrows(), 1):
                        coluna_ranking = 'Sinergia' if tipo_mancha == 'Apenas Sinergia' else 'Forca_Conjunta'
                        valor = row[coluna_ranking]
                        st.markdown(f"**{i}.** {row['nome']}<br><small>{valor:.1%}</small>", unsafe_allow_html=True)
                else:
                    st.info("Nenhum dado disponível para ranking")
        
    else:
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT))
        st.info("Nenhum dado para exibir no mapa com os filtros atuais.")

# --- SEÇÃO DE ANÁLISE DETALHADA ---
st.divider()
st.header("Análise Detalhada por Agrupamento")

# **ALTERAÇÃO AQUI: A seção inteira foi reescrita para ser interativa e mais completa**
if modo_analise == "Visão Geral":
    if not df_filtrado.empty:
        analysis_col1, analysis_col2 = st.columns([1, 3])

        with analysis_col1:
            mapa_agrupamento = {
                "Bairro": "NOME_BAIRRO",
                "Zona Eleitoral": "NR_ZONA",
                "Local de Votação": "NM_LOCAL_VOTACAO"
            }
            nivel_analise = st.radio(
                "Analisar por:",
                options=list(mapa_agrupamento.keys()),
                horizontal=False,
                key="nivel_analise_radio"
            )
            coluna_agrupamento = mapa_agrupamento[nivel_analise]

            # Dicionário de opções de ordenação
            opcoes_ordenacao = {
                "Padrão (Alfabética)": ("index", True),
                "Mais Votos (F. Paes)": ("Votos F. Paes", False),
                "Mais Votos (Í. Armelau)": ("Votos Í. Armelau", False),
                "Maior Volume Total de Votos": ("Total de Votos", False),
                "Maior Vantagem (F. Paes)": ("Diferença (Paes - Armelau)", False),
                "Maior Vantagem (Í. Armelau)": ("Diferença (Paes - Armelau)", True),
            }
            ordenacao_selecionada = st.selectbox(
                "Ordenar por:",
                options=list(opcoes_ordenacao.keys())
            )

        with analysis_col2:
            search_term = st.text_input(
                f"Pesquisar por {nivel_analise}:",
                placeholder="Digite para filtrar a tabela...",
                key=f"search_{nivel_analise}"
            )
            
            df_analise = df_filtrado.pivot_table(
                index=coluna_agrupamento,
                columns=COLUNA_CANDIDATO,
                values='QT_VOTOS_TOTAL',
                aggfunc='sum'
            ).fillna(0).astype(int)

            if NOME_FERNANDO not in df_analise.columns: df_analise[NOME_FERNANDO] = 0
            if NOME_INDIA not in df_analise.columns: df_analise[NOME_INDIA] = 0
                
            df_analise.rename(columns={
                NOME_FERNANDO: "Votos F. Paes",
                NOME_INDIA: "Votos Í. Armelau"
            }, inplace=True)

            # Adiciona colunas para total e diferença
            df_analise["Total de Votos"] = df_analise["Votos F. Paes"] + df_analise["Votos Í. Armelau"]
            df_analise["Diferença (Paes - Armelau)"] = df_analise["Votos F. Paes"] - df_analise["Votos Í. Armelau"]

                        # Adiciona a coluna com a porcentagem da diferença
            epsilon = 1e-9 # Evita divisão por zero
            df_analise["Diferença (%)"] = (df_analise["Diferença (Paes - Armelau)"].abs() / (df_analise["Total de Votos"] + epsilon)) * 100

            # Aplica o filtro de pesquisa
            if search_term:
                df_analise = df_analise[
                    df_analise.index.astype(str).str.contains(search_term, case=False, na=False)
                ]

            # Aplica a ordenação selecionada
            coluna_sort, ascendente = opcoes_ordenacao[ordenacao_selecionada]
            if coluna_sort == "index":
                df_display = df_analise.sort_index(ascending=ascendente)
            else:
                df_display = df_analise.sort_values(by=coluna_sort, ascending=ascendente)

            # Estilização do DataFrame com cores
            def color_paes(val):
                return f'color: {COR_FERNANDO}'
            def color_india(val):
                return f'color: {COR_INDIA}'

            styled_df = df_display.style.applymap(color_paes, subset=['Votos F. Paes']) \
                                        .applymap(color_india, subset=['Votos Í. Armelau']) \
                                        .format({"Diferença (%)": "{:.1f}%"})
            
            st.dataframe(styled_df, use_container_width=True)

    else:
        st.info("Nenhum dado para exibir na análise detalhada com os filtros atuais.")
else:
    st.info("Selecione o modo 'Visão Geral' para ver a análise detalhada por agrupamento.")
