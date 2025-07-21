import streamlit as st
import pandas as pd
import pydeck as pdk
import geopandas as gpd

# --- CONFIGURAÇÃO DA PÁGINA ---

st.set_page_config(
    page_title="Análise Interativa de Votação - Município do Rio de Janeiro",
    page_icon="📈",
    layout="wide",
)

st.title("Análise Interativa de Votação - Município do Rio de Janeiro")

# --- CONSTANTES ---
COLUNA_CANDIDATO = 'NM_VOTAVEL'
NOME_FERNANDO = 'FERNANDO CESAR CAMPOS PAES'
NOME_INDIA = 'AMANDA BRANDAO ARMELAU'
URL_GEOJSON_ESTADO_RIO = "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-33-mun.json"
URL_GEOJSON_BAIRROS_RIO = "https://pgeo3.rio.rj.gov.br/arcgis/rest/services/Cartografia/Limites_administrativos/MapServer/4/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"
COR_FERNANDO = "#008000"  # Verde
COR_INDIA = "#FFA500"     # Laranja
RGB_FERNANDO = [0, 128, 0]
RGB_INDIA = [255, 165, 0]


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
            if len(digits) > 7:
                s_clean = f"{'-' if is_neg else ''}{digits[:2]}.{digits[2:]}"
            else:
                s_clean = f"{'-' if is_neg else ''}{digits[:3]}.{digits[3:]}"
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

    gdf_estado = gpd.read_file(URL_GEOJSON_ESTADO_RIO)
    gdf_municipio = gdf_estado[gdf_estado['name'] == 'Rio de Janeiro']
    return df_com_bairro, gdf_municipio, gdf_bairros

# --- CARREGAMENTO DOS DADOS ---
df_original, municipio_rj_geo, bairros_rj_geo = carregar_dados()


# --- EXIBIÇÃO DOS TOTAIS DE VOTOS ---
votos_fernando = int(df_original[df_original[COLUNA_CANDIDATO] == NOME_FERNANDO]['QT_VOTOS_TOTAL'].sum())
votos_india = int(df_original[df_original[COLUNA_CANDIDATO] == NOME_INDIA]['QT_VOTOS_TOTAL'].sum())

col1, col2, _ = st.columns(3)
col1.metric(label=f"Total de Votos - {NOME_FERNANDO}", value=f"{votos_fernando:,}".replace(",", "."))
col2.metric(label=f"Total de Votos - {NOME_INDIA}", value=f"{votos_india:,}".replace(",", "."))
st.divider()

# --- FILTROS NA PÁGINA PRINCIPAL ---
st.subheader("Filtros de Visualização")
filt_col1, filt_col2, filt_col3 = st.columns([1, 1, 2])

with filt_col1:
    modo_analise = st.radio("Modo de Análise:", ("Comparativo (Locais em Comum)", "Visão Geral (Ambos)", "Apenas Fernando Paes", "Apenas Índia Armelau"), index=0)

df_pre_filtro = df_original.copy()
if modo_analise == "Apenas Fernando Paes":
    df_pre_filtro = df_original[df_original[COLUNA_CANDIDATO] == NOME_FERNANDO]
elif modo_analise == "Apenas Índia Armelau":
    df_pre_filtro = df_original[df_original[COLUNA_CANDIDATO] == NOME_INDIA]
elif modo_analise == "Comparativo (Locais em Comum)":
    locais_comuns = df_original.groupby('NM_LOCAL_VOTACAO').filter(lambda x: len(x[COLUNA_CANDIDATO].unique()) == 2)['NM_LOCAL_VOTACAO'].unique()
    df_pre_filtro = df_original[df_original['NM_LOCAL_VOTACAO'].isin(locais_comuns)]


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
    else:
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
        ("Pontos", "Mapa de Calor", "Por Bairro"),
        index=0,
        help="'Pontos': vencedor por local. 'Mapa de Calor': concentração de votos. 'Por Bairro': vencedor por bairro."
    )
    st.divider()

    if tipo_visualizacao == "Por Bairro":
        if modo_analise in ["Comparativo (Locais em Comum)", "Visão Geral (Ambos)"]:
            st.markdown("**Disputa no Bairro:**")
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {COR_FERNANDO}; border-radius: 5px; margin-right: 10px;"></div><span>Vitória de F. Paes</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 15px;"><div style="width: 20px; height: 20px; background-color: {COR_INDIA}; border-radius: 5px; margin-right: 10px;"></div><span>Vitória de Í. Armelau</span></div>', unsafe_allow_html=True)
            st.markdown("**Intensidade da Cor:**<p style='font-size: 0.9em;'>Quanto mais <b>forte</b> a cor, <b>mais equilibrada</b> (menor diferença percentual) foi a votação no bairro.</p>", unsafe_allow_html=True)
        else:
            candidato_selecionado = "Fernando Paes" if modo_analise == "Apenas Fernando Paes" else "Índia Armelau"
            cor_base_html = COR_FERNANDO if candidato_selecionado == "Fernando Paes" else COR_INDIA
            st.markdown(f"**Concentração de Votos:**")
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {cor_base_html}; border-radius: 5px; margin-right: 10px;"></div><span>Votos de {candidato_selecionado}</span></div>', unsafe_allow_html=True)
            st.markdown("**Intensidade da Cor:**<p style='font-size: 0.9em;'>Quanto mais <b>forte</b> a cor, <b>maior</b> o número absoluto de votos para o candidato no bairro.</p>", unsafe_allow_html=True)

    elif tipo_visualizacao == "Pontos" and not df_mapa.empty:
        if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
            candidato_selecionado = "Fernando Paes" if modo_analise == "Apenas Fernando Paes" else "Índia Armelau"
            cor_base_html = COR_FERNANDO if candidato_selecionado == "Fernando Paes" else COR_INDIA
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {cor_base_html}; border-radius: 50%; margin-right: 10px;"></div><span>{candidato_selecionado}</span></div>', unsafe_allow_html=True)
        else:
            modo_cor = st.radio("Colorir pontos por:", ("Sinergia (Relativa %)", "Sinergia (Absoluta)", "Magnitude da Vitória", "Volume de Votos (Ponderado)"))
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="width: 20px; height: 20px; background-color: {COR_FERNANDO}; border-radius: 50%; margin-right: 10px;"></div><span>Fernando Paes</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="display: flex; align-items: center; margin-bottom: 15px;"><div style="width: 20px; height: 20px; background-color: {COR_INDIA}; border-radius: 50%; margin-right: 10px;"></div><span>Índia Armelau</span></div>', unsafe_allow_html=True)

    elif tipo_visualizacao == "Mapa de Calor":
        if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
            candidato_selecionado = "Fernando Paes" if modo_analise == "Apenas Fernando Paes" else "Índia Armelau"
            st.markdown(f"O mapa de calor visualiza a **concentração de votos** de **{candidato_selecionado}**.")
        else:
            st.markdown("O mapa de calor visualiza a **sinergia** de votos.")

# --- RENDERIZAÇÃO DO MAPA ---
with map_col:
    view_state = pdk.ViewState(latitude=-22.9068, longitude=-43.1729, zoom=9.5, pitch=0)
    polygon_layer = pdk.Layer("GeoJsonLayer", data=municipio_rj_geo, get_fill_color="[220, 220, 220, 40]", get_line_color="[0, 0, 0, 100]", get_line_width=30)

    if not df_filtrado.empty and 'NOME_BAIRRO' in df_filtrado.columns:
        if tipo_visualizacao == "Por Bairro":
            if modo_analise in ["Comparativo (Locais em Comum)", "Visão Geral (Ambos)"]:
                df_bairros_agg = df_filtrado.pivot_table(index='NOME_BAIRRO', columns=COLUNA_CANDIDATO, values='QT_VOTOS_TOTAL', aggfunc='sum').fillna(0)
                if NOME_FERNANDO not in df_bairros_agg: df_bairros_agg[NOME_FERNANDO] = 0
                if NOME_INDIA not in df_bairros_agg: df_bairros_agg[NOME_INDIA] = 0
                df_bairros_agg[NOME_FERNANDO] = df_bairros_agg[NOME_FERNANDO].astype(int)
                df_bairros_agg[NOME_INDIA] = df_bairros_agg[NOME_INDIA].astype(int)
                df_bairros_agg['Diferenca'] = df_bairros_agg[NOME_FERNANDO] - df_bairros_agg[NOME_INDIA]
                df_bairros_agg['Total_Votos'] = df_bairros_agg[NOME_FERNANDO] + df_bairros_agg[NOME_INDIA]
                df_bairros_agg['Diferenca_Absoluta'] = df_bairros_agg['Diferenca'].abs()
                epsilon = 1e-9
                df_bairros_agg['Sinergia'] = 1 - (df_bairros_agg['Diferenca_Absoluta'] / (df_bairros_agg['Total_Votos'] + epsilon))

                gdf_bairros_plot = bairros_rj_geo.merge(df_bairros_agg, left_on='nome', right_index=True, how='left').fillna(0)
                
                # --- CORREÇÃO: LÓGICA DE NORMALIZAÇÃO DA COR ---
                bairros_com_votos = gdf_bairros_plot[gdf_bairros_plot['Total_Votos'] > 0]
                min_sinergia = bairros_com_votos['Sinergia'].min()
                max_sinergia = bairros_com_votos['Sinergia'].max()
                range_sinergia = max_sinergia - min_sinergia if max_sinergia > min_sinergia else 1.0

                def get_bairro_color_comparativo(row):
                    base_color = RGB_FERNANDO if row['Diferenca'] > 0 else RGB_INDIA
                    if row['Total_Votos'] > 0:
                        normalized_sinergia = (row['Sinergia'] - min_sinergia) / range_sinergia
                        # Usa uma potência para dar mais peso visual às diferenças
                        adjusted_sinergia = normalized_sinergia ** 0.75
                        alpha = int(50 + adjusted_sinergia * 205)
                    else:
                        alpha = 20
                    return base_color + [alpha]
                # --- FIM DA CORREÇÃO ---

                gdf_bairros_plot['cor'] = gdf_bairros_plot.apply(get_bairro_color_comparativo, axis=1)
                gdf_bairros_plot['tooltip'] = gdf_bairros_plot.apply(
                    lambda r: f"<b>Bairro: {r['nome']}</b><br>"
                            f"F. Paes: {int(r[NOME_FERNANDO])}<br>"
                            f"Í. Armelau: {int(r[NOME_INDIA])}<br>"
                            f"<b>Diferença: {int(r['Diferenca'])}</b><br>"
                            f"<i>Sinergia: {r['Sinergia']:.1%}</i>", axis=1)
            else:
                candidato_selecionado = NOME_FERNANDO if modo_analise == "Apenas Fernando Paes" else NOME_INDIA
                cor_base_rgb = RGB_FERNANDO if modo_analise == "Apenas Fernando Paes" else RGB_INDIA
                
                df_bairros_agg = df_filtrado.groupby('NOME_BAIRRO')['QT_VOTOS_TOTAL'].sum().reset_index()
                gdf_bairros_plot = bairros_rj_geo.merge(df_bairros_agg, left_on='nome', right_on='NOME_BAIRRO', how='left').fillna(0)
                max_votos_bairro = gdf_bairros_plot['QT_VOTOS_TOTAL'].max() or 1
                
                def get_bairro_color_unico(votos):
                    alpha = 50 + int((votos / max_votos_bairro) * 205)
                    return cor_base_rgb + [alpha]

                gdf_bairros_plot['cor'] = gdf_bairros_plot['QT_VOTOS_TOTAL'].apply(get_bairro_color_unico)
                gdf_bairros_plot['tooltip'] = gdf_bairros_plot.apply(
                    lambda r: f"<b>Bairro: {r['nome']}</b><br>"
                            f"Votos: {int(r['QT_VOTOS_TOTAL'])}", axis=1)

            bairro_layer = pdk.Layer(
                "GeoJsonLayer", data=gdf_bairros_plot, opacity=0.7, pickable=True,
                get_fill_color='cor', get_line_color=[0, 0, 0, 100], get_line_width=15,
            )
            st.pydeck_chart(pdk.Deck(layers=[polygon_layer, bairro_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT, tooltip={"html": "{tooltip}"}))
        
        elif tipo_visualizacao == "Pontos":
            if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
                max_votos_unico = df_mapa['Votos_Candidato_Unico'].max() or 1
                cor_base_rgb = RGB_FERNANDO if modo_analise == "Apenas Fernando Paes" else RGB_INDIA
                df_mapa['cor'] = df_mapa['Votos_Candidato_Unico'].apply(lambda x: cor_base_rgb + [int(50 + (x / max_votos_unico) * 205)])
                df_mapa['raio'] = df_mapa['Votos_Candidato_Unico'].apply(lambda x: 100 + (x / max_votos_unico * 400))
                df_mapa['tooltip'] = df_mapa.apply(lambda r: f"<b>{r['NM_LOCAL_VOTACAO']}</b><br>Votos: {r['Votos_Candidato_Unico']}", axis=1)
            else:
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

        else: # Renderiza o Mapa de Calor
            if modo_analise in ["Apenas Fernando Paes", "Apenas Índia Armelau"]:
                heatmap_weight_col = 'Votos_Candidato_Unico'
            else:
                heatmap_weight_col = 'Sinergia_Peso'
            heatmap_layer = pdk.Layer(
                "HeatmapLayer", data=df_mapa, opacity=0.9, get_position='[lon, lat]',
                get_weight=heatmap_weight_col, radius_pixels=25, intensity=2, threshold=0.03
            )
            st.pydeck_chart(pdk.Deck(layers=[polygon_layer, heatmap_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT))
    else:
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer], initial_view_state=view_state, map_style=pdk.map_styles.CARTO_LIGHT))
        st.info("Nenhum dado para exibir no mapa com os filtros atuais.")

# --- SEÇÃO DE ANÁLISE DETALHADA ---
st.divider()
st.header("Rankings e Análises Detalhadas")

if modo_analise in ["Comparativo (Locais em Comum)", "Visão Geral (Ambos)"]:
    if not df_mapa.empty:
        df_analise = df_mapa.set_index('NM_LOCAL_VOTACAO')
        df_analise['Diferença Absoluta'] = df_analise['Diferença'].abs()
        df_analise_com_votos = df_analise[df_analise['Total_Votos'] > 0].copy()

        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Maiores Vitórias (Paes)", "🏆 Maiores Vitórias (Índia)", "🤝 Votações Mais Próximas", "🗳️ Maiores Votações (Soma)"])

        def display_ranking(tab, title, dataframe, sort_by, ascending, cols_to_show, key_prefix):
            with tab:
                st.subheader(title)
                top_n = st.number_input("Mostrar Top N:", min_value=5, max_value=100, value=10, step=5, key=f"num_{key_prefix}")
                st.dataframe(dataframe.sort_values(by=sort_by, ascending=ascending).head(top_n)[cols_to_show], use_container_width=True)

        display_ranking(tab1, "Locais com Maior Vantagem para Fernando Paes", df_analise, 'Diferença', False, [NOME_FERNANDO, NOME_INDIA, 'Diferença'], "paes_win")
        display_ranking(tab2, "Locais com Maior Vantagem para Índia Armelau", df_analise, 'Diferença', True, [NOME_FERNANDO, NOME_INDIA, 'Diferença Absoluta'], "india_win")
        display_ranking(tab3, "Locais com Votações Mais Parecidas", df_analise_com_votos, 'Diferença Absoluta', True, [NOME_FERNANDO, NOME_INDIA, 'Diferença Absoluta'], "proximos")
        display_ranking(tab4, "Locais com Maior Soma de Votos", df_analise, 'Total_Votos', False, ['Total_Votos', NOME_FERNANDO, NOME_INDIA], "total")

        st.divider()
        st.header("Desempenho nos Maiores Colégios Eleitorais")
        st.markdown("Comparativo do número de votos nos 40 locais com maior volume total de votação (respeitando os filtros aplicados).")

        df_grafico_linha = df_analise.sort_values(by='Total_Votos', ascending=False).head(40)
        st.line_chart(df_grafico_linha[[NOME_INDIA, NOME_FERNANDO]], color=[COR_INDIA, COR_FERNANDO])
    else:
        st.info("Nenhum dado para exibir nos rankings e gráficos para os filtros atuais.")
else:
    st.info("Selecione um modo de análise comparativo para ver os rankings e gráficos detalhados.")