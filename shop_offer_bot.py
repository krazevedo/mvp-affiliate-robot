# Versão 1.0 - O Robô Caçador de Lojas (Completo)
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
SHOPEE_API_URL = "https://open-api.affiliate.shpee.com.br/graphql"

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
# SUA MISSÃO: Substitua esta lista pelos IDs de LOJA que você encontrar!
SHOP_IDS_PARA_MONITORAR = [369632653, 288420684, 286277644, 1157280425, 1315886500, 349591196, 886950101] # Exemplo de ID da documentação
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 3 # Quantas das melhores ofertas de todas as lojas serão postadas

# --- 3. FUNÇÕES AUXILIARES (Copiadas do robô principal para independência) ---
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