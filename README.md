# ✈️ Monitor de Preços de Passagens

Uma aplicação web moderna para monitorar preços de passagens aéreas e receber alertas quando encontrar boas ofertas!

## 🚀 Funcionalidades

### ✨ Interface Web Moderna
- **Interface Gradio** intuitiva e responsiva
- **Duas abas principais**: Verificar Preços e Monitoramento Contínuo
- **Design moderno** com emojis e cores atrativas

### 🔍 Verificação de Preços
- Busca preços de passagens por origem, destino e data
- Exibe resultados em tabela organizada
- Mostra companhia aérea, preço, horário e detalhes da viagem

### 📊 Monitoramento Contínuo
- Configuração de preço alvo personalizado
- Intervalo de verificação ajustável (5-60 minutos)
- Sistema de alertas automáticos para preços baixos
- Monitoramento em background

## 🛠️ Tecnologias Utilizadas

- **Python 3.13**
- **Gradio** - Interface web
- **Requests** - Requisições HTTP
- **BeautifulSoup4** - Parseamento HTML
- **Pandas** - Manipulação de dados
- **Urllib3** - Estratégia de retry

## 📦 Instalação

### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd alarme_precos
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Execute a aplicação
```bash
python main.py
```

### 4. Acesse a interface
- **URL local**: `http://127.0.0.1:7860`
- **URL pública**: Será mostrada no terminal

## 📖 Como Usar

### Aba "Verificar Preços"
1. **Origem**: Digite a cidade de partida (ex: São Paulo)
2. **Destino**: Digite a cidade de chegada (ex: Recife)
3. **Data**: Digite a data da viagem (ex: 2024-02-15)
4. **Clique** em "🔍 Verificar Preços"
5. **Veja** os resultados na tabela

### Aba "Monitoramento Contínuo"
1. **Configure** origem, destino e data
2. **Defina** um preço alvo (ex: R$ 300)
3. **Escolha** o intervalo de verificação (5-60 minutos)
4. **Clique** em "🚀 Iniciar Monitoramento"
5. **Receba** alertas quando encontrar preços baixos

## 🏗️ Estrutura do Projeto

```
alarme_precos/
├── main.py                 # Aplicação principal com interface Gradio
├── alternative_approach.py # Abordagem alternativa para web scraping
├── requirements.txt        # Dependências do projeto
└── README.md              # Este arquivo
```

## 🔧 Arquitetura do Código

### Classe `FlightPriceMonitor`
```python
class FlightPriceMonitor:
    def __init__(self):
        # Configuração da sessão HTTP
        
    def setup_session(self):
        # Headers e estratégia de retry
        
    def check_flight_price(self, origin, destination, date):
        # Verificação de preços
        
    def monitor_prices(self, origin, destination, target_date, target_price, update_interval):
        # Monitoramento contínuo
```

### Interface Gradio
- **Tabs**: Organização em abas para diferentes funcionalidades
- **Inputs**: Campos de texto, números e sliders
- **Outputs**: Tabelas e caixas de texto para resultados
- **Callbacks**: Funções executadas ao clicar nos botões

## ⚠️ Limitações Atuais

### Simulação de Preços
- **Status**: Aplicação atual simula preços para demonstração
- **Motivo**: Sites de viagem bloqueiam bots com proteções anti-scraping
- **Solução**: Implementar APIs reais ou Selenium WebDriver

### Proteções Anti-Bot
Sites como Decolar, Latam, etc. usam:
- Detecção de User-Agent
- Análise de comportamento
- Verificação de cookies
- Proteção por IP
- Captchas

## 🚀 Próximos Passos

### 1. Integração com APIs Reais
- [ ] API da Skyscanner
- [ ] API do Google Flights
- [ ] APIs de companhias aéreas

### 2. Melhorias na Interface
- [ ] Gráficos de preços ao longo do tempo
- [ ] Histórico de preços
- [ ] Filtros por companhia aérea
- [ ] Notificações push

### 3. Funcionalidades Avançadas
- [ ] Selenium WebDriver para sites protegidos
- [ ] Sistema de notificações (email, WhatsApp)
- [ ] Banco de dados para histórico
- [ ] Múltiplas rotas simultâneas

### 4. Deploy e Produção
- [ ] Deploy no Hugging Face Spaces
- [ ] Configuração de CI/CD
- [ ] Monitoramento de performance
- [ ] Backup automático

## 🐛 Solução de Problemas

### Erro 403 (Forbidden)
- **Causa**: Site bloqueia requisições automatizadas
- **Solução**: Use a abordagem alternativa ou APIs oficiais

### Dependências não encontradas
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Porta já em uso
```bash
# A aplicação tentará automaticamente a próxima porta disponível
# Ou especifique uma porta diferente no código
```

## 📝 Exemplo de Uso

```python
# Executar a aplicação
python main.py

# Acessar no navegador
# http://localhost:7860

# Configurar monitoramento
# Origem: São Paulo
# Destino: Recife
# Data: 2024-02-15
# Preço alvo: R$ 300
# Intervalo: 15 minutos
```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 📞 Suporte

Se você encontrar algum problema ou tiver sugestões:
- Abra uma issue no GitHub
- Entre em contato através do email
- Consulte a documentação das bibliotecas utilizadas

---

**Desenvolvido com ❤️ para ajudar você a encontrar as melhores ofertas de passagens!**