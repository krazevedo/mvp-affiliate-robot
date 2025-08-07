# Versão 10 - Preparada para a Nuvem (Render.com)
import requests
import time
import hashlib
import json
import random
import os # Essencial para ler variáveis de ambiente
import math # Precisaremos de matemática para a pontuação

# --- CONFIGURAÇÕES VINDAS DAS VARIÁVEIS DE AMBIENTE ---
# O script vai ler estas informações do ambiente da Render, não mais diretamente do código.
SHOPEE_PARTNER_ID = int(os.environ.get("SHOPEE_PARTNER_ID"))
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# URL da API da Shopee (não mexer)
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# --- NOVAS CONFIGURAÇÕES ---
HISTORICO_PRODUTOS_ARQUIVO = "historico_produtos.json"

PALAVRAS_CHAVE_DE_BUSCA = [
    "caixa de som bluetooth",
    "fone de ouvido sem fio",
    "smartwatch",
    "teclado mecanico",
    "mouse gamer",
    "air fryer"
]
# Quantos dos melhores produtos serão postados ao final de todo o ciclo
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 3
# Quantas páginas de resultados buscar por palavra-chave para criar a lista de candidatos
PAGINAS_A_VERIFICAR_POR_KEYWORD = 3 

# --- FUNÇÕES AUXILIARES (sem alteração) ---
def carregar_historico():
    if not os.path.exists(HISTORICO_PRODUTOS_ARQUIVO): return set()
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'r') as f:
        try: return set(json.load(f))
        except json.JSONDecodeError: return set()

def salvar_no_historico(item_id):
    historico = carregar_historico()
    historico.add(item_id)
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'w') as f: json.dump(list(historico), f)

def enviar_mensagem_telegram(mensagem):
    print("Enviando mensagem para o Telegram...")
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
    try:
        response = requests.post(telegram_api_url, json=payload)
        response_json = response.json()
        if response_json.get("ok"):
            print("Mensagem enviada com sucesso!")
            return True
        else:
            print(f"--- ERRO TELEGRAM ---: {response_json.get('description')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com a API do Telegram: {e}")
        return False

# --- NOVAS FUNÇÕES DE LÓGICA ---
def calcular_pontuacao(produto):
    pontuacao = 0
    PESO_DESCONTO = 1.5
    PESO_AVALIACAO = 1.0
    PESO_VENDAS = 0.8
    
    desconto = produto.get('priceDiscountRate', 0)
    if desconto: pontuacao += float(desconto) * PESO_DESCONTO
        
    avaliacao = produto.get('ratingStar', "0")
    if avaliacao: pontuacao += float(avaliacao) * PESO_AVALIACAO
        
    vendas = produto.get('sales', 0)
    if vendas and vendas > 0: pontuacao += math.log10(vendas) * PESO_VENDAS

    return pontuacao

def coletar_ofertas_candidatas(palavras_chave, paginas_a_verificar, historico):
    print("Iniciando FASE 1: Coleta de Ofertas Candidatas...")
    ofertas_candidatas = []
    itens_por_pagina = 20

    for palavra in palavras_chave:
        print(f"  - Coletando da keyword: '{palavra}'...")
        for pagina_atual in range(1, paginas_a_verificar + 1):
            timestamp = int(time.time())
            graphql_query = """query { productOfferV2(keyword: "%s", limit: %d, page: %d) { nodes { itemId productName priceMin priceMax offerLink shopName ratingStar sales priceDiscountRate } } }""" % (keyword, itens_por_pagina, pagina_atual)
            body = {"query": graphql_query, "variables": {}}
            payload_str = json.dumps(body, separators=(',', ':'))
            base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
            sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
            auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
            headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}
            
            try:
                response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
                data = response.json()
                if "errors" in data and data["errors"]: print(f"    Erro Shopee: {data['errors']}"); break
                product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                if not product_list: break
                
                for produto in product_list:
                    if produto.get('itemId') not in historico:
                        ofertas_candidatas.append(produto)
            except Exception as e: print(f"    Erro na requisição: {e}"); break
            time.sleep(2)
            
    ofertas_unicas = list({prod['itemId']: prod for prod in ofertas_candidatas}.values())
    print(f"Coleta finalizada. {len(ofertas_unicas)} ofertas novas encontradas.")
    return ofertas_unicas

if __name__ == "__main__":
    print("🤖 Robô Curador Iniciado (v13) 🤖")
    
    # FASE 1: Coleta
    historico_atual = carregar_historico()
    candidatos = coletar_ofertas_candidatas(PALAVRAS_CHAVE_DE_BUSCA, PAGINAS_A_VERIFICAR_POR_KEYWORD, historico_atual)

    if not candidatos:
        print("Nenhuma nova oferta encontrada para análise. Ciclo finalizado.")
    else:
        # FASE 2: Análise e Pontuação
        print("\nIniciando FASE 2: Análise e Pontuação das Ofertas...")
        for produto in candidatos:
            produto['pontuacao'] = calcular_pontuacao(produto)
        
        # Ordena os candidatos pela maior pontuação
        candidatos_ordenados = sorted(candidatos, key=lambda p: p['pontuacao'], reverse=True)
        print(f"Análise finalizada. Melhor oferta: '{candidatos_ordenados[0]['productName']}' com score {candidatos_ordenados[0]['pontuacao']:.2f}")

        # FASE 3: Publicação Seletiva
        print(f"\nIniciando FASE 3: Publicação das {QUANTIDADE_DE_POSTS_POR_EXECUCAO} Melhores Ofertas...")
        for i, melhor_produto in enumerate(candidatos_ordenados[:QUANTIDADE_DE_POSTS_POR_EXECUCAO]):
            print(f"  - Postando oferta Top {i+1}...")
            mensagem = (
                f"<b>🏆 OFERTA COM ALTA PONTUAÇÃO 🏆</b>\n\n"
                f"<b>Produto:</b> {melhor_produto.get('productName')}\n"
                f"<b>Loja:</b> {melhor_produto.get('shopName')}\n"
                f"<b>Preço:</b> R$ {melhor_produto.get('priceMin')}\n"
                f"<b>Nota do Robô:</b> {melhor_produto.get('pontuacao'):.2f} / 100\n\n"
                f"<a href='{melhor_produto.get('offerLink')}'><b>🛒 Ver a Melhor Oferta</b></a>"
            )
            if enviar_mensagem_telegram(mensagem):
                salvar_no_historico(melhor_produto.get('itemId'))
    
    print("\n✅ Ciclo do Robô Curador finalizado.")