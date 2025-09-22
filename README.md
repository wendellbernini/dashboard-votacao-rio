# Dashboard de Análise Eleitoral - Rio de Janeiro

Dashboard interativo para análise de votação dos candidatos Fernando Paes e Índia Armelau no município do Rio de Janeiro.

## 🚀 Deploy na Vercel

### Pré-requisitos
- Conta na [Vercel](https://vercel.com)
- Repositório no GitHub

### Passos para Deploy

1. **Fazer push do código para o GitHub**
   ```bash
   git add .
   git commit -m "Preparar para deploy na Vercel"
   git push origin main
   ```

2. **Conectar na Vercel**
   - Acesse [vercel.com](https://vercel.com)
   - Clique em "New Project"
   - Importe seu repositório do GitHub
   - Configure:
     - **Framework Preset**: Other
     - **Root Directory**: ./
     - **Build Command**: (deixe vazio)
     - **Output Directory**: (deixe vazio)

3. **Variáveis de Ambiente** (se necessário)
   - Na Vercel, vá em Settings > Environment Variables
   - Adicione se necessário:
     - `STREAMLIT_SERVER_PORT=8501`
     - `STREAMLIT_SERVER_ADDRESS=0.0.0.0`

4. **Deploy**
   - Clique em "Deploy"
   - Aguarde o processo (pode demorar alguns minutos)

### ⚠️ Limitações da Vercel

- **Timeout**: A Vercel tem limite de 10 segundos para funções serverless
- **Streamlit**: Pode não funcionar perfeitamente devido às limitações de tempo
- **Alternativa**: Considere usar [Railway](https://railway.app) ou [Heroku](https://heroku.com)

## 🛠️ Execução Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
streamlit run app.py
```

## 📊 Funcionalidades

- **Visualização por Pontos**: Mostra locais de votação com intensidade baseada no total de votos
- **Mancha de Votos**: Visualização por bairros com cores baseadas na força eleitoral
- **Análise de Sinergia**: Identifica áreas de forte parceria eleitoral
- **Exportação**: Baixe dados em CSV/JSON e mapas em PDF
- **Filtros**: Por bairro, zona eleitoral e candidato

## 📁 Estrutura de Arquivos

```
├── app.py                          # Aplicação principal
├── votacao_com_coordenadas.csv     # Dados eleitorais
├── requirements.txt                # Dependências Python
├── vercel.json                     # Configuração Vercel
├── Procfile                        # Configuração Heroku
├── runtime.txt                     # Versão Python
└── README.md                       # Este arquivo
```

## 🔧 Tecnologias

- **Streamlit**: Framework web
- **PyDeck**: Visualização de mapas
- **GeoPandas**: Manipulação de dados geoespaciais
- **Pandas**: Análise de dados
- **Plotly**: Gráficos interativos
