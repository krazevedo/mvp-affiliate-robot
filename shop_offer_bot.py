# Versão Final - O Robô Caçador de Lojas (Completo e Corrigido)
import requests
import time
import hashlib
import json
import random
import os
import sys
import math
import google.generativeai as genai
from thefuzz import fuzz

# --- 1. CONFIGURAÇÕES GERAIS E SEGREDOS ---
print("--- INICIANDO VERIFICAÇÃO DE VARIÁVEIS DE AMBIENTE ---")
SHOPEE_PARTNER_ID_STR = os.environ.get("SHOPEE_PARTNER_ID")
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not all([SHOPEE_PARTNER_ID_STR, SHOPEE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY]):
    print("\nERRO CRÍTICO: Segredos não carregados.")
    sys.exit(1)

SHOPEE_PARTNER_ID = int(SHOPEE_PARTNER_ID_STR)
# CORREÇÃO CRUCIAL: URL estava com erro de digitação ("shpee")
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

try:
    print("Configurando a IA do Gemini...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("IA configurada com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO AO CONFIGURAR A IA: {e}")
    sys.exit(1)

# --- 2. PARÂMETROS DO CAÇADOR DE LOJAS ---
HISTORICO_PRODUTOS_ARQUIVO = "historico_produtos.json"
SHOP_IDS_PARA_MONITORAR = [84499012] # Lembre-se de substituir pelos IDs de loja que você pesquisou
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 2

# --- 3. FUNÇÕES AUXILIARES COMPLETAS ---
def carregar_historico():
    if not os.path.exists(HISTORICO_PRODUTOS_ARQUIVO): return {}
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except json.JSONDecodeError: return {}

def salvar_no_historico(produto, historico):
    item_id = str(produto.get('itemId'))
    historico[item_id] = {
        "productName": produto.get('productName'),
        "priceMin": float(produto.get('priceMin', 0)),
        "lastPostedTimestamp": int(time.time())
    }
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

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

def calcular_pontuacao(produto):
    try:
        pontuacao = 0.0
        if not produto.get('ratingStar') or float(produto.get('ratingStar', "0")) < 4.0: return 0.0
        desconto = produto.get('priceDiscountRate'); avaliacao = float(produto.get('ratingStar', "0")); vendas = produto.get('sales')
        if desconto is not None: pontuacao += float(desconto) * 1.5
        if avaliacao is not None: pontuacao += avaliacao * 1.0
        if vendas is not None and vendas > 0: pontuacao += math.log10(vendas) * 0.8
        return pontuacao
    except (ValueError, TypeError): return 0.0

def gerar_texto_com_ia(produto):
    print(f"    - Gerando texto com IA para '{produto.get('productName')}'...")
    try:
        prompt = (f"Você é um especialista em marketing para um canal de ofertas. Crie uma chamada curta e empolgante (máximo 3 frases, use emojis) para o produto: '{produto.get('productName')}'. Foque nos benefícios.")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    - Erro ao gerar texto com IA: {e}")
        return f"✨ Confira esta super oferta! ✨\n\n{produto.get('productName')}"

def verificar_link_ativo(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if response.status_code == 200 and "O produto não existe" not in response.text:
            return True
    except requests.exceptions.RequestException:
        return False
    return False

# --- 4. LÓGICA PRINCIPAL DO CAÇADOR DE LOJAS ---
def buscar_ofertas_de_loja(shop_id, historico_ids):
    print(f"\nBuscando ofertas para o Shop ID: {shop_id}...")
    ofertas_encontradas = []
    
    graphql_query = """query { shopOfferV2(shopId: %d, limit: 20, sortType: 3) { nodes { itemId, productName, priceMin, priceMax, offerLink, productLink, shopName, ratingStar, sales, priceDiscountRate } } }""" % (shop_id)

    timestamp = int(time.time())
    body = {"query": graphql_query, "variables": {}}
    payload_str = json.dumps(body, separators=(',', ':'))
    base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
    sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
    auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
    headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}

    try:
        response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
        data = response.json()
        if "errors" in data and data["errors"]:
            print(f"    Erro Shopee: {data['errors']}")
            return []
        
        product_list = data.get("data", {}).get("shopOfferV2", {}).get("nodes", [])
        print(f"  - Encontrados {len(product_list)} produtos brutos na loja.")

        for produto in product_list:
            if int(produto.get('itemId')) in historico_ids:
                continue
            link_original = produto.get("productLink")
            if not link_original or not verificar_link_ativo(link_original):
                continue
            ofertas_encontradas.append(produto)
            
    except Exception as e:
        print(f"    - Erro na requisição para a loja {shop_id}: {e}")

    print(f"  - Encontradas {len(ofertas_encontradas)} novas e válidas ofertas para a loja {shop_id}.")
    return ofertas_encontradas

# --- 5. EXECUÇÃO ---
if __name__ == "__main__":
    print("🤖 Robô Caçador de Lojas Iniciado (v1.0 - Operacional) 🤖")
    historico_completo = carregar_historico()
    historico_ids = {int(item_id) for item_id in historico_completo.keys()}

    todas_as_ofertas_de_loja = []
    for shop_id in SHOP_IDS_PARA_MONITORAR:
        novas_ofertas = buscar_ofertas_de_loja(shop_id, historico_ids)
        todas_as_ofertas_de_loja.extend(novas_ofertas)
        time.sleep(3)
    
    if not todas_as_ofertas_de_loja:
        print("\nNenhuma nova oferta de loja encontrada neste ciclo.")
    else:
        for produto in todas_as_ofertas_de_loja:
            produto['pontuacao'] = calcular_pontuacao(produto)
        
        ofertas_ordenadas = sorted(todas_as_ofertas_de_loja, key=lambda p: p['pontuacao'], reverse=True)
        
        print(f"\nPublicando as melhores {QUANTIDADE_DE_POSTS_POR_EXECUCAO} ofertas de loja encontradas...")
        for produto_final in ofertas_ordenadas[:QUANTIDADE_DE_POSTS_POR_EXECUCAO]:
            texto_ia = gerar_texto_com_ia(produto_final)
            loja = produto_final.get('shopName')
            
            mensagem = (
                f"🛍️ **OFERTA ESPECIAL DA LOJA {loja.upper()}** 🛍️\n\n"
                f"{texto_ia}\n\n"
                f"<b>💰 Preço:</b> A partir de R$ {produto_final.get('priceMin')}\n"
                f"<b>⭐ Avaliação:</b> {produto_final.get('ratingStar')} estrelas\n\n"
                f"<a href='{produto_final.get('offerLink')}'><b>🛒 Ver na Loja</b></a>"
            )

            if enviar_mensagem_telegram(mensagem):
                salvar_no_historico(produto_final, historico_completo)

    print("\n✅ Ciclo do Caçador de Lojas finalizado.")