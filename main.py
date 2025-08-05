
# NSFW Bot - Project Eros v2.1 com 5 fontes

import discord
from discord.ext import commands
import aiohttp
from bs4 import BeautifulSoup
import asyncio
import re
import json
import os
import random

TOKEN = os.getenv("DISCORD_TOKEN")
CATEGORIA_BASE = "╍╍╍CATEGORIES"
RESULTADOS_POR_CANAL = 3
INTERVALO_LOOP = 3
ARQUIVO_HISTORICO = 'historico.json'
ARQUIVO_CONFIG = 'config.json'
HEADERS = {'User-Agent': 'NSFWBot/2.0 (https://github.com/you)'}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

if not os.path.exists(ARQUIVO_HISTORICO):
    with open(ARQUIVO_HISTORICO, 'w') as f:
        json.dump({}, f)

if not os.path.exists(ARQUIVO_CONFIG):
    with open(ARQUIVO_CONFIG, 'w') as f:
        json.dump({}, f)

with open(ARQUIVO_HISTORICO, 'r') as f:
    historico = json.load(f)

with open(ARQUIVO_CONFIG, 'r') as f:
    configuracoes = json.load(f)

def salvar_historico():
    with open(ARQUIVO_HISTORICO, 'w') as f:
        json.dump(historico, f, indent=2)

def salvar_config():
    with open(ARQUIVO_CONFIG, 'w') as f:
        json.dump(configuracoes, f, indent=2)

def ja_enviado(canal_id, link):
    return link in historico.get(str(canal_id), [])

def registrar_envio(canal_id, link):
    canal_str = str(canal_id)
    historico.setdefault(canal_str, []).append(link)
    salvar_historico()

def formatar_nome_canal(nome):
    nome = nome.lower()
    nome = re.sub(r'[^a-z0-9\s-]', '', nome)
    nome = nome.replace("vídeo", "").replace("video", "")
    return nome.strip()

async def garantir_nsfw(canal):
    if not canal.is_nsfw():
        try:
            await canal.edit(nsfw=True)
        except:
            pass

async def listar_canais_categoria(guild):
    categorias = [c for c in guild.categories if c.name.startswith(CATEGORIA_BASE)]
    canais = []
    for cat in categorias:
        canais.extend([c for c in cat.channels if isinstance(c, discord.TextChannel)])
    return canais

# === Scrapers ===

async def buscar_gelbooru(session, query, max_results=5):
    try:
        url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags={query}&limit=50"
        async with session.get(url, headers=HEADERS) as r:
            data = await r.json()
            return [{'url': p['file_url'], 'title': p.get('tags', '')} for p in data][:max_results]
    except:
        return []

async def buscar_rule34(session, query, max_results=5):
    try:
        url = f"https://rule34.xxx/index.php?page=dapi&s=post&q=index&tags={query}&limit=50"
        async with session.get(url, headers=HEADERS) as r:
            text = await r.text()
            soup = BeautifulSoup(text, 'xml')
            return [{'url': p['file_url'], 'title': p.get('tags', '')} for p in soup.find_all('post')][:max_results]
    except:
        return []

async def buscar_e621(session, query, max_results=5):
    try:
        url = f"https://e621.net/posts.json?tags={query}&limit=50"
        async with session.get(url, headers=HEADERS) as r:
            data = await r.json()
            return [{'url': p['file']['url'], 'title': " ".join(p.get('tags', {}).get('general', []))} for p in data['posts'] if 'file' in p][:max_results]
    except:
        return []

async def buscar_danbooru(session, query, max_results=5):
    try:
        url = f"https://danbooru.donmai.us/posts.json?tags={query}&limit=50"
        async with session.get(url, headers=HEADERS) as r:
            data = await r.json()
            return [{'url': p['file_url'], 'title': " ".join(p.get('tag_string', '').split())} for p in data if 'file_url' in p][:max_results]
    except:
        return []

async def buscar_xbooru(session, query, max_results=5):
    try:
        url = f"https://xbooru.com/index.php?page=dapi&s=post&q=index&tags={query}&limit=50"
        async with session.get(url, headers=HEADERS) as r:
            text = await r.text()
            soup = BeautifulSoup(text, 'xml')
            return [{'url': p['file_url'], 'title': p.get('tags', '')} for p in soup.find_all('post')][:max_results]
    except:
        return []

SCRAPERS = {
    "gelbooru": buscar_gelbooru,
    "rule34": buscar_rule34,
    "e621": buscar_e621,
    "danbooru": buscar_danbooru,
    "xbooru": buscar_xbooru
}

def verificar_todas_palavras(title, palavras_chave):
    title = title.lower()
    return all(palavra in title for palavra in palavras_chave)

async def enviar_conteudo_para_canal(canal, resultados, palavras_chave):
    canal_id = str(canal.id)
    config = configuracoes.get(canal_id, {"modo": "random", "porcentagem_video": 50})

    enviados = 0
    random.shuffle(resultados)

    for item in resultados:
        url = item.get('url')
        title = item.get('title', '')

        if not url or ja_enviado(canal.id, url):
            continue

        is_video = url.endswith(('.mp4', '.webm'))
        is_imagem = url.endswith(('.jpg', '.png', '.gif'))

        if config["modo"] == "custom":
            chance_video = config["porcentagem_video"]
            roleta = random.randint(1, 100)

            if roleta <= chance_video and not is_video:
                continue
            if roleta > chance_video and not is_imagem:
                continue

        try:
            await canal.send(url)
            registrar_envio(canal.id, url)
            enviados += 1
            await asyncio.sleep(1)
        except:
            continue

        if enviados >= RESULTADOS_POR_CANAL:
            break

async def processar(canal, session):
    nome_formatado = formatar_nome_canal(canal.name)
    palavras_chave = nome_formatado.split()

    if not palavras_chave:
        return

    await garantir_nsfw(canal)

    resultados = []
    for scraper in SCRAPERS.values():
        try:
            dados = await scraper(session, "+".join(palavras_chave), 20)
            resultados.extend(dados)
        except:
            continue

    unicos = {item['url']: item for item in resultados}.values()
    await enviar_conteudo_para_canal(canal, list(unicos), palavras_chave)

async def loop_inteligente():
    await bot.wait_until_ready()
    async with aiohttp.ClientSession() as session:
        while not bot.is_closed():
            for guild in bot.guilds:
                canais = await listar_canais_categoria(guild)
                for canal in canais:
                    await processar(canal, session)
                    await asyncio.sleep(1)  # Ajuda a reduzir o ritmo

@bot.command()
async def midia(ctx, modo: str):
    canal_id = str(ctx.channel.id)
    config = configuracoes.get(canal_id, {"modo": "random", "porcentagem_video": 50})

    if modo.lower() == "random":
        config["modo"] = "random"
        await ctx.send("🌀 Modo aleatório ativado! O bot enviará qualquer tipo de mídia.")
    elif modo.isdigit() and 0 <= int(modo) <= 100:
        config["modo"] = "custom"
        config["porcentagem_video"] = int(modo)
        await ctx.send(f"🎯 Bot ajustado para {modo}% vídeos e {100 - int(modo)}% imagens.")
    else:
        await ctx.send("❌ Use `.midia <0-100>` ou `.midia random`")

    configuracoes[canal_id] = config
    salvar_config()

@bot.event
async def on_ready():
    print(f"[✅ ONLINE] Logado como {bot.user}")
    bot.loop.create_task(loop_inteligente())

bot.run(TOKEN)
