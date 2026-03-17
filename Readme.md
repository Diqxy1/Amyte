<div align="center">

# 🎮 Amyte

**Bot Discord open source para ver sua loja do Valorant direto no Discord**

[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1483520532866531390&permissions=8&integration_type=0&scope=bot+applications.commands)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[**➕ Adicionar ao servidor**](https://discord.com/oauth2/authorize?client_id=1483520532866531390&permissions=8&integration_type=0&scope=bot+applications.commands) • [**top.gg**](https://top.gg/bot/SEU_CLIENT_ID) • [**Suporte**](https://discord.gg/SEU_INVITE)

</div>

---

## ✨ Comandos

| Comando | Descrição |
|---------|-----------|
| `/store` | Mostra as 4 skins da sua loja diária |
| `/nightmarket` | Mostra as ofertas do mercado noturno |
| `/kcstore` | Mostra a loja semanal de Kingdom Credits |
| `/wallet` | Mostra seu saldo de VP, Radianite e KC |
| `/rank` | Mostra seu rank competitivo atual |
| `/help` | Lista todos os comandos |

> Todos os comandos também funcionam com o prefix `!` (ex: `!store br`)

---

## 🌍 Regiões suportadas

`br` · `na` · `eu` · `ap` · `kr` · `latam`

---

## 🔐 Segurança e privacidade

Este bot usa autenticação via **cookie `ssid`** da Riot Games.

- ✅ **Nenhuma senha** é solicitada ou armazenada
- ✅ O `ssid` é **descartado imediatamente** após a autenticação
- ✅ Código **100% open source** — verifique você mesmo
- ✅ Resultados enviados via **DM** ou canal, à sua escolha
- ⚠️ O `ssid` concede acesso temporário à conta — use apenas bots que você confia

---

## 🚀 Self-hosting (rodar você mesmo)

### Pré-requisitos
- Python 3.11+
- Bot criado no [Discord Developer Portal](https://discord.com/developers/applications)

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/Diqxy1/Amyte
cd valorant-store-bot

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o .env
cp .env.example .env
# Edite o .env e adicione seu TOKEN do Discord

# 5. Inicie o bot
python main.py
```

### Variáveis de ambiente

```env
TOKEN=seu_token_do_discord_aqui
PREFIX=!
```

---

## 📖 Como usar o `/store`

1. Digite `/store` (ou `!store br`) no servidor
2. O bot envia uma DM com instruções para obter o `ssid`
3. Siga os passos, copie o cookie e responda a DM
4. Escolha se quer ver o resultado na DM ou no canal
5. Pronto! 🎉

### Como obter o cookie `ssid`

1. Acesse `https://auth.riotgames.com` e faça login
2. Pressione **F12** → aba **Application** (Chrome) ou **Storage** (Firefox)
3. Vá em **Cookies** → `https://auth.riotgames.com`
4. Copie o valor do cookie `ssid`

---

## 🗂️ Estrutura do projeto

```
valorant-store-bot/
├── main.py              # Entry point
├── config.py            # Configurações via .env
├── requirements.txt
├── cogs/
│   ├── general.py       # /ping, /help, !clear
│   └── store.py         # /store, /nightmarket, /wallet, /rank, /kcstore
├── services/
│   ├── auth.py          # Autenticação via cookie ssid
│   └── store.py         # Busca loja, wallet, rank e KC store
└── utils/
    ├── embeds.py        # Construtores de embeds Discord
    └── logger.py        # Logging estruturado
```

---

## ⚠️ Aviso legal

Este bot usa a API **não-oficial** do Valorant. O uso pode violar os [Termos de Serviço da Riot Games](https://www.riotgames.com/en/terms-of-service). Use por sua conta e risco. Este projeto não é afiliado à Riot Games.

---

## 📄 Licença

MIT © Diqxy1