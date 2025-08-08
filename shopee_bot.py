# Versão 18 - O Robô Vigilante de Preços (Completo e Final)
import requests, time, hashlib, json, random, os, sys, math
import google.generativeai as genai
from thefuzz import fuzz

# --- CONFIGURAÇÕES GERAIS E SEGREDOS ---
SHOPEE_PARTNER_ID_STR = os.environ.get("SHOPEE_PARTNER_ID")
SHOPEE_API_KEY = os.environ.get("SHOPEE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not all([SHOPEE_PARTNER_ID_STR, SHOPEE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY]):
    print("\nERRO CRÍTICO: Segredos não carregados.")
    sys.exit(1)

SHOPEE_PARTNER_ID = int(SHOPEE_PARTNER_ID_STR)
SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"

try:
    print("Configurando a IA do Gemini...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("IA configurada com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO AO CONFIGURAR A IA: {e}")
    sys.exit(1)

# --- PARÂMETROS DE CURADORIA E VIGILÂNCIA ---
HISTORICO_PRODUTOS_ARQUIVO = "historico_produtos.json"
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 3
PAGINAS_A_VERIFICAR_POR_KEYWORD = 3
LIMIAR_DE_DESCONTO_REPOSTAGEM = 0.15  # 15%
COOLDOWN_REPOSTAGEM_DIAS = 7

TEMPLATES_ALERTA_PRECO = [
    ("🚨 **BAIXOU O PREÇO!** 🚨\n\n"
     "<b>{productName}</b>\n\n"
     "📉 De R$ {preco_antigo:.2f} por apenas <b>R$ {priceMin:.2f}</b>! Uma queda de <b>{desconto_percentual}%</b>!\n"
     "🏪 Loja: {shopName}\n\n"
     "<a href='{offerLink}'><b>🏃‍♂️ Corre pra garantir antes que o preço suba!</b></a>")
]

# --- FUNÇÕES AUXILIARES ---
def carregar_keywords(caminho_arquivo="keywords.txt"):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            keywords = [linha.strip() for linha in f if linha.strip()]
            print(f"Carregadas {len(keywords)} palavras-chave de {caminho_arquivo}.")
            return keywords
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{caminho_arquivo}' não encontrado.")
        return []

PALAVRAS_CHAVE_DE_BUSCA = carregar_keywords()

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
    # (Cole aqui a função completa da v16)
    pass 

def calcular_pontuacao(produto):
    # (Cole aqui a função completa da v16)
    pass

def gerar_texto_com_ia(produto):
    # (Cole aqui a função completa da v16)
    pass

def verificar_link_ativo(url):
    # (Cole aqui a função completa da v17)
    pass

def eh_duplicata(novo_produto, historico):
    # (Cole aqui a função completa da v17)
    pass

def coletar_ofertas_candidatas(palavras_chave, paginas_a_verificar):
    print("\n[FASE 1] Iniciando Coleta de Ofertas...")
    ofertas_candidatas = []
    itens_por_pagina = 15
    for palavra in palavras_chave:
        print(f"  - Buscando keyword: '{palavra}'...")
        for pagina_atual in range(1, paginas_a_verificar + 1):
            timestamp = int(time.time())
            graphql_query = """query { productOfferV2(keyword: "%s", limit: %d, page: %d) { nodes { itemId productName priceMin priceMax offerLink productLink shopName ratingStar sales priceDiscountRate } } }""" % (palavra, itens_por_pagina, pagina_atual)
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
                    print(f"    Erro Shopee na página {pagina_atual}: {data['errors']}")
                    break 
                product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                if not product_list:
                    print(f"    Nenhum produto na página {pagina_atual}. Finalizando busca para esta keyword.")
                    break
                print(f"    Página {pagina_atual}: {len(product_list)} produtos brutos encontrados.")
                ofertas_candidatas.extend(product_list)
            except Exception as e:
                print(f"    Erro na requisição: {e}")
                break
            time.sleep(2)
    ofertas_unicas = list({str(prod.get('itemId')): prod for prod in ofertas_candidatas}.values())
    print(f"Coleta finalizada. {len(ofertas_unicas)} ofertas candidatas únicas encontradas.")
    return ofertas_unicas

# --- EXECUÇÃO PRINCIPAL REESTRUTURADA ---
# (Cole aqui o bloco if __name__ == "__main__" completo da v18)