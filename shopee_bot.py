# Versão 16 - Depuração Final e Detalhada
import requests
import time
import hashlib
import json
import random
import os
import sys
import math
import google.generativeai as genai

# --- 1. VERIFICAÇÃO DAS VARIÁVEIS DE AMBIENTE ---
print("--- INICIANDO VERIFICAÇÃO DE VARIÁVEIS DE AMBIENTE ---")
# ... (código de verificação da v15.1, que já sabemos que funciona) ...
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
    model = genai.GenerativeModel('gemini-pro')
    print("IA configurada com sucesso.")
except Exception as e:
    print(f"ERRO CRÍTICO AO CONFIGURAR A IA: {e}")
    sys.exit(1)

# --- PARÂMETROS E FUNÇÕES (sem alteração) ---
HISTORICO_PRODUTOS_ARQUIVO = "historico_produtos.json"
PALAVRAS_CHAVE_DE_BUSCA = ["caixa de som bluetooth", "fone de ouvido sem fio", "smartwatch", "teclado mecanico", "mouse gamer", "air fryer", "projetor hy300", "camera de segurança"]
QUANTIDADE_DE_POSTS_POR_EXECUCAO = 2
PAGINAS_A_VERIFICAR_POR_KEYWORD = 2

def carregar_historico():
    if not os.path.exists(HISTORICO_PRODUTOS_ARQUIVO): return set()
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'r') as f:
        try:
            data = json.load(f)
            # Garante que o histórico seja sempre um conjunto de inteiros
            return set(int(item) for item in data)
        except (json.JSONDecodeError, ValueError): return set()

def salvar_no_historico(item_id):
    historico = carregar_historico()
    historico.add(int(item_id))
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
    print("\n[FASE 1] Iniciando Coleta e Pontuação...")
    ofertas_por_keyword = {kw: [] for kw in palavras_chave}
    itens_por_pagina = 10
    for palavra in palavras_chave:
        print(f"  - Buscando keyword: '{palavra}'...")
        for pagina_atual in range(1, paginas_a_verificar + 1):
            timestamp = int(time.time())
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
                if "errors" in data and data["errors"]: print(f"    Erro Shopee: {data['errors']}"); break
                product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
                if not product_list: print(f"    Nenhum produto na página {pagina_atual}."); break
                
                print(f"    Página {pagina_atual}: {len(product_list)} produtos encontrados.")
                novos_nesta_pagina = 0
                for produto in product_list:
                    item_id = int(produto.get('itemId'))
                    if item_id not in historico:
                        produto['pontuacao'] = calcular_pontuacao(produto)
                        ofertas_por_keyword[palavra].append(produto)
                        novos_nesta_pagina += 1
                if novos_nesta_pagina == 0: print("    Todos os produtos desta página já estão no histórico.")
                        
            except Exception as e: print(f"    Erro na requisição: {e}"); break
            time.sleep(2)
    print("Coleta finalizada.")
    return ofertas_por_keyword

# --- EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    print(f"\n🤖 Robô Curador com IA Iniciado (v16 - Debug Final)")
    
    historico_atual = carregar_historico()
    print(f"Carregado histórico com {len(historico_atual)} itens.")

    ofertas_por_categoria = coletar_e_pontuar_ofertas(PALAVRAS_CHAVE_DE_BUSCA, PAGINAS_A_VERIFICAR_POR_KEYWORD, historico_atual)
    
    print("\n[FASE 2] Iniciando Seleção das Melhores Ofertas...")
    melhores_ofertas = []
    for palavra, ofertas in ofertas_por_categoria.items():
        if ofertas:
            print(f"  - Categoria '{palavra}' tem {len(ofertas)} novas ofertas.")
            melhor_da_categoria = sorted(ofertas, key=lambda p: p['pontuacao'], reverse=True)[0]
            melhores_ofertas.append(melhor_da_categoria)
        else:
            print(f"  - Categoria '{palavra}' não tem novas ofertas.")
    
    if not melhores_ofertas:
        print("\nNenhuma nova oferta encontrada em nenhuma categoria para análise. Ciclo finalizado.")
    else:
        melhores_ofertas_gerais = sorted(melhores_ofertas, key=lambda p: p['pontuacao'], reverse=True)
        print(f"Seleção finalizada. {len(melhores_ofertas_gerais)} ofertas finalistas escolhidas.")
        
        print(f"\n[FASE 3] Iniciando Publicação das {QUANTIDADE_DE_POSTS_POR_EXECUCAO} Melhores...")
        for i, produto_final in enumerate(melhores_ofertas_gerais[:QUANTIDADE_DE_POSTS_POR_EXECUCAO]):
            print(f"  - Processando oferta Top {i+1}: '{produto_final['productName']}'")
            # (A lógica de gerar texto com IA e enviar para o Telegram vai aqui)
            # ...
            pass # Substitua pelo código de postagem real

    print("\n✅ Ciclo do Robô Curador com IA concluído com sucesso.")