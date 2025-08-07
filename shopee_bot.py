# Versão 10 - Preparada para a Nuvem (Render.com)
import requests
import time
import hashlib
import json
import random
import os # Essencial para ler variáveis de ambiente

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

# Lista de templates para as mensagens. Sinta-se à vontade para adicionar mais!
TEMPLATES_MENSAGENS = [
    (
        "<b>✨ OFERTA IMPERDÍVEL ✨</b>\n\n"
        "<b>{productName}</b>\n\n"
        "💰 Preço a partir de: <b>R$ {priceMin}</b>\n"
        "🏪 Loja: {shopName}\n\n"
        "<a href='{offerLink}'><b>👉 Ver Oferta Agora</b></a>"
    ),
    (
        "<b>🔥 ACHADO DO DIA 🔥</b>\n\n"
        "{productName}\n\n"
        "📉 Por apenas <b>R$ {priceMin}</b>!\n"
        "<a href='{offerLink}'><b>🛒 Comprar Agora</b></a>\n\n"
        "<i>Vendido por: {shopName}</i>"
    ),
    (
        "<b>⚡️ CORRE QUE ACABA! ⚡️</b>\n\n"
        "Olha o que eu encontrei pra vocês:\n"
        "<b>{productName}</b>\n\n"
        "💸 Preços entre R$ {priceMin} e R$ {priceMax}\n"
        "<a href='{offerLink}'><b>✅ EU QUERO!</b></a>"
    ),
]

# --- FUNÇÕES ---

def carregar_historico():
    """Carrega os IDs dos produtos já postados a partir de um arquivo JSON."""
    if not os.path.exists(HISTORICO_PRODUTOS_ARQUIVO):
        return set() # Retorna um conjunto vazio se o arquivo não existe
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'r') as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()

def salvar_no_historico(item_id):
    """Salva um novo ID de produto no arquivo de histórico."""
    historico = carregar_historico()
    historico.add(item_id)
    with open(HISTORICO_PRODUTOS_ARQUIVO, 'w') as f:
        json.dump(list(historico), f)

def enviar_mensagem_telegram(mensagem):
    # (Esta função permanece a mesma da v8)
    print("Enviando mensagem para o Telegram...")
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem,
        'parse_mode': 'HTML', 'disable_web_page_preview': False
    }
    try:
        response = requests.post(telegram_api_url, json=payload)
        response_json = response.json()
        if response_json.get("ok"):
            print("Mensagem enviada com sucesso para o Telegram!")
            return True
        else:
            print(f"--- ERRO AO ENVIAR PARA O TELEGRAM ---: {response_json.get('description')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão com a API do Telegram: {e}")
        return False

def buscar_e_postar_oferta_shopee(keyword, limit=5):
    """
    Função principal com verificação de histórico e templates aleatórios.
    """
    print("Iniciando busca de ofertas na Shopee...")
    historico = carregar_historico()
    print(f"{len(historico)} produtos já estão no histórico.")
    
    # ... (código da API da Shopee - permanece o mesmo da v7) ...
    timestamp = int(time.time())
    graphql_query = """query { productOfferV2(keyword: "%s", limit: %d) { nodes { itemId productName priceMin priceMax offerLink shopName ratingStar imageUrl } } }""" % (keyword, limit)
    body = {"query": graphql_query, "variables": {}}
    payload_str = json.dumps(body, separators=(',', ':'))
    base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
    sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
    auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
    headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}
    # ... (fim do código da API da Shopee) ...
    
    try:
        response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
        data = response.json()
        if "errors" in data and data["errors"]: print(f"Erro Shopee: {data['errors']}"); return

        product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
        if not product_list: print(f"Nenhum produto encontrado para: '{keyword}'"); return
        
        print(f"Encontradas {len(product_list)} ofertas. Verificando histórico...")
        ofertas_postadas = 0
        for produto in product_list:
            item_id = produto.get('itemId')
            if item_id in historico:
                print(f"Produto '{produto.get('productName')}' (ID: {item_id}) já está no histórico. Ignorando.")
                continue

            # Escolhe um template de mensagem aleatoriamente
            template_escolhido = random.choice(TEMPLATES_MENSAGENS)
            
            # Formata a mensagem com os dados do produto
            mensagem_formatada = template_escolhido.format(
                productName=produto.get('productName'),
                priceMin=produto.get('priceMin'),
                priceMax=produto.get('priceMax'),
                shopName=produto.get('shopName'),
                offerLink=produto.get('offerLink')
            )
            
            # Envia para o Telegram e, se tiver sucesso, salva no histórico
            if enviar_mensagem_telegram(mensagem_formatada):
                salvar_no_historico(item_id)
                ofertas_postadas += 1
                print(f"Produto '{produto.get('productName')}' postado e salvo no histórico.")
        
        print(f"\nBusca finalizada. {ofertas_postadas} nova(s) oferta(s) postada(s).")

    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

def buscar_e_postar_novas_ofertas(keyword, novas_ofertas_desejadas=1):
    """
    Função principal com lógica de paginação para encontrar ofertas inéditas.
    """
    historico = carregar_historico()
    print(f"Histórico atual contém {len(historico)} produtos.")

    # --- NOVA LÓGICA DE PAGINAÇÃO ---
    pagina_atual = 1
    ofertas_postadas_nesta_busca = 0
    MAX_PAGINAS_A_VERIFICAR = 5 # Limite de segurança
    LIMITE_DE_ITENS_POR_PAGINA = 10 # Quantos itens pedir por página para a API

    while ofertas_postadas_nesta_busca < novas_ofertas_desejadas and pagina_atual <= MAX_PAGINAS_A_VERIFICAR:
        print(f"\nVerificando página {pagina_atual} para a keyword '{keyword}'...")
        
        timestamp = int(time.time())
        # A query agora inclui o parâmetro 'page'
        graphql_query = """query { productOfferV2(keyword: "%s", limit: %d, page: %d) { nodes { itemId productName priceMin priceMax offerLink shopName ratingStar imageUrl } } }""" % (keyword, LIMITE_DE_ITENS_POR_PAGINA, pagina_atual)
        
        # (O restante da lógica de autenticação e chamada da API permanece o mesmo)
        body = {"query": graphql_query, "variables": {}}
        payload_str = json.dumps(body, separators=(',', ':'))
        base_string = f"{SHOPEE_PARTNER_ID}{timestamp}{payload_str}{SHOPEE_API_KEY}"
        sign = hashlib.sha256(base_string.encode('utf-8')).hexdigest()
        auth_header = f"SHA256 Credential={SHOPEE_PARTNER_ID}, Timestamp={timestamp}, Signature={sign}"
        headers = {'Authorization': auth_header, 'Content-Type': 'application/json'}

        try:
            response = requests.post(SHOPEE_API_URL, data=payload_str, headers=headers)
            data = response.json()
            if "errors" in data and data["errors"]: print(f"Erro Shopee: {data['errors']}"); break

            product_list = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
            if not product_list:
                print("Nenhum produto retornado nesta página. Encerrando busca para esta keyword.")
                break
            
            produtos_novos_na_pagina = 0
            for produto in product_list:
                item_id = produto.get('itemId')
                if item_id in historico:
                    continue # Pula para o próximo produto da lista se já estiver no histórico

                # Se chegamos aqui, o produto é novo!
                produtos_novos_na_pagina += 1
                template_escolhido = random.choice(TEMPLATES_MENSAGENS)
                mensagem_formatada = template_escolhido.format(**produto) # Truque para preencher o template
                
                if enviar_mensagem_telegram(mensagem_formatada):
                    salvar_no_historico(item_id)
                    ofertas_postadas_nesta_busca += 1
                    print(f"✅ Nova oferta '{produto.get('productName')}' postada e salva no histórico.")
                    if ofertas_postadas_nesta_busca >= novas_ofertas_desejadas:
                        break # Sai do loop for se já atingimos a meta
            
            if produtos_novos_na_pagina == 0:
                print("Todos os produtos desta página já estão no histórico.")

            pagina_atual += 1 # Prepara para buscar na próxima página no próximo loop

        except Exception as e:
            print(f"Ocorreu um erro inesperado na busca: {e}")
            break # Interrompe a busca para esta keyword em caso de erro

    return ofertas_postadas_nesta_busca


if __name__ == "__main__":
    NOVAS_OFERTAS_POR_PALAVRA = 1 # Quantas ofertas novas queremos postar para cada keyword
    
    print("🤖 Robô de Ofertas Iniciado - v12 com Paginação Inteligente 🤖")
    
    for palavra in PALAVRAS_CHAVE_DE_BUSCA:
        print("\n" + "="*50)
        print(f"🔎 Buscando {NOVAS_OFERTAS_POR_PALAVRA} nova(s) oferta(s) para: '{palavra}'")
        print("="*50)
        
        buscar_e_postar_novas_ofertas(palavra, novas_ofertas_desejadas=NOVAS_OFERTAS_POR_PALAVRA)
        
        print("\n🕒 Pausa de 5 segundos antes da próxima busca...")
        time.sleep(5)
        
    print("\n✅ Ciclo de busca finalizado.")