# Versão 10 - Preparada para a Nuvem (Render.com)
import requests
import time
import hashlib
import json
import random
import os # Essencial para ler variáveis de ambiente
import math # Precisaremos de matemática para a pontuação
import google.generativeai as genai
import sys

# --- CONFIGURAÇÕES VINDAS DAS VARIÁVEIS DE AMBIENTE ---
# O script vai ler estas informações do ambiente da Render, não mais diretamente do código.
SHOPEE_PARTNER_ID = int(os.environ.get("SHOPEE_PARTNER_ID"))
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Imprime o status de cada variável para depuração
print(f"SHOPEE_PARTNER_ID: {'Carregado' if SHOPEE_PARTNER_ID else 'NÃO ENCONTRADO'}")
print(f"SHOPEE_API_KEY: {'Carregado' if SHOPEE_API_KEY else 'NÃO ENCONTRADO'}")
print(f"TELEGRAM_BOT_TOKEN: {'Carregado' if TELEGRAM_BOT_TOKEN else 'NÃO ENCONTRADO'}")
print(f"TELEGRAM_CHAT_ID: {'Carregado' if TELEGRAM_CHAT_ID else 'NÃO ENCONTRADO'}")
print(f"GEMINI_API_KEY: {'Carregado' if GEMINI_API_KEY else 'NÃO ENCONTRADO'}")

# Validação Crítica: Se alguma chave estiver faltando, o robô para aqui.
if not all([SHOPEE_PARTNER_ID, SHOPEE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY]):
    print("\nERRO CRÍTICO: Uma ou mais variáveis de ambiente (segredos) não foram carregadas. Verifique as configurações no GitHub.")
    sys.exit(1) # Encerra o script com um código de erro

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

# --- CONFIGURAÇÃO DA IA ---
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
model = genai.GenerativeModel('gemini-pro', generation_config=generation_config)

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

def gerar_texto_com_ia(produto):
    """Gera um texto de venda persuasivo usando a IA do Gemini."""
    print(f"    - Gerando texto com IA para '{produto['productName']}'...")
    try:
        prompt = (
            "Você é um especialista em marketing digital e copywriter para um canal de ofertas no Telegram chamado 'Conexão Descontos'. "
            f"Sua tarefa é criar uma chamada curta, empolgante e persuasiva para o seguinte produto: '{produto['productName']}'.\n"
            "Regras:\n"
            "- Use no máximo 3 frases.\n"
            "- Use emojis que combinem com o produto (🔥, ✨, ⚡️, 🚀, etc.).\n"
            "- Foque nos benefícios e na sensação de oportunidade única.\n"
            "- Não mencione o preço ou a loja, apenas o produto.\n"
            "- O texto deve ser em português do Brasil.\n"
            "Exemplo: '🚀 Leve sua música para outro nível! Perfeita para qualquer festa, essa caixa de som entrega um som potente e cristalino. Não perca essa chance de garantir a sua!'"
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"    - Erro ao gerar texto com IA: {e}")
        return f"✨ Confira esta super oferta! ✨\n\n{produto['productName']}" # Fallback

def coletar_e_pontuar_ofertas(palavras_chave, paginas_a_verificar, historico):
    print("Iniciando FASE 1: Coleta e Pontuação de Ofertas...")
    ofertas_candidatas = []
    itens_por_pagina = 20

    for palavra in palavras_chave:
        print(f"  - Coletando da keyword: '{palavra}'...")
        for pagina_atual in range(1, paginas_a_verificar + 1):
            timestamp = int(time.time())
            # A query agora precisa pedir os campos 'sales' e 'priceDiscountRate' para a pontuação
            graphql_query = """query { productOfferV2(keyword: "%s", limit: %d, page: %d) { nodes { itemId productName priceMin priceMax offerLink shopName ratingStar sales priceDiscountRate } } }""" % (palavra, itens_por_pagina, pagina_atual)
            
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
                    break 
                
                # A variável 'product_list' é definida AQUI
                product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                
                if not product_list:
                    print(f"    Nenhum produto retornado na página {pagina_atual}.")
                    break
                
                # E usada AQUI, agora na ordem correta
                for produto in product_list:
                    if produto.get('itemId') not in historico:
                        produto['pontuacao'] = calcular_pontuacao(produto) # Calcula a pontuação durante a coleta
                        ofertas_candidatas.append(produto)

            except Exception as e:
                print(f"    Erro na requisição: {e}")
                break
            
            time.sleep(2)
            
    ofertas_unicas = list({prod['itemId']: prod for prod in ofertas_candidatas}.values())
    print(f"\nColeta finalizada. {len(ofertas_unicas)} ofertas novas e únicas encontradas.")
    return ofertas_unicas