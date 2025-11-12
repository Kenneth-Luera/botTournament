import re
import aiohttp
import discord
from discord import Intents
from datetime import timezone
import comandos
import os


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "http://127.0.0.1:8000/api/api/discord-logs/"
API_SECRET = os.getenv("API_SECRET")
LOG_CHANNEL_ID = 1310003020658118708
TARGET_BOT_ID = 1310003511123120219

intents = Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

client = discord.Client(intents=intents)

RE_LICENSE_LINE = re.compile(
    r"License:\s*license:(?P<license_id>[a-f0-9]{32})",
    re.IGNORECASE
)
RE_PLAYER_DETAILS = re.compile(r"Player Details:\s*(?P<details>.+)", re.IGNORECASE)
RE_TIME = re.compile(r"\[?(?P<hour>\d{1,2}:\d{2})\]?")

async def send_to_api(payload: dict):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=payload, headers={"X-Discord-Secret": API_SECRET}) as resp:
                text = await resp.text()
                if resp.status in (200, 201):
                    print("Enviado a API:", payload)
                else:
                    print("API respondió:", resp.status, text)
        except Exception as e:
            print("Error conectando a API:", e)

def parse_embed_content(message: discord.Message):

    players = []
    content_parts = []

    if message.embeds:
        for emb in message.embeds:
            if emb.description:
                content_parts.append(str(emb.description))

    if message.content:
        content_parts.append(message.content)

    joined = "\n".join(content_parts)

    license_matches = list(RE_LICENSE_LINE.finditer(joined))
    details_matches = list(RE_PLAYER_DETAILS.finditer(joined))

    for idx, m in enumerate(license_matches):
        license_id = m.group("license_id")
        player_details = details_matches[idx].group("details").strip() if idx < len(details_matches) else "Desconocido"
        players.append({
            "license": license_id,
            "player_details": player_details
        })

    time_match = RE_TIME.search(joined)
    hora = time_match.group("hour") if time_match else message.created_at.replace(tzinfo=timezone.utc).isoformat()

    return joined, players, hora 

@client.event
async def on_ready():
    print("Bot listo:", client.user)

@client.event
async def on_message(message):
    if message.author.id != TARGET_BOT_ID or message.channel.id != LOG_CHANNEL_ID:
        return

    if not message.embeds and not message.content:
        print("El mensaje del bot está vacío")
        return

    joined_content, players, hora = parse_embed_content(message)

    print("Contenido completo del embed/mensaje:")
    print(joined_content)

    if not players:
        print("No se encontraron 'license' en el mensaje del bot.")
        return

    payload = {
        "event_type": "DEATH_LOG",
        "guild_id": str(message.guild.id) if message.guild else None,
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "time_of_death": hora,
        "players": players
    }

    if len(players) == 2:
        payload["killer"] = players[0]
        payload["victim"] = players[1]

    await send_to_api(payload)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)