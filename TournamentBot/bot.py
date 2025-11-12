import re
import aiohttp
import discord
from discord import Intents
from datetime import timezone
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_URL = "http://127.0.0.1:8000/api/api/discord-logs/"
API_SECRET = os.getenv("API_SECRET")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
TARGET_BOT_ID = int(os.getenv("TARGET_BOT_ID"))

intents = Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True

client = discord.Client(intents=intents)

# Expresiones regulares
RE_LICENSE_LINE = re.compile(r"License:\s*license:(?P<license_id>[a-f0-9]{32})", re.IGNORECASE)
RE_PLAYER_DETAILS = re.compile(r"Player Details:\s*(?P<details>.+)", re.IGNORECASE)
RE_TIME = re.compile(r"\[?(?P<hour>\d{1,2}:\d{2})\]?")

# === FUNCIONES ===

async def send_to_api(payload: dict):
    """Envía el JSON a tu API Django."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, json=payload, headers={"X-Discord-Secret": API_SECRET}) as resp:
                text = await resp.text()
                if resp.status in (200, 201):
                    print("✅ Enviado a API:", payload)
                else:
                    print(f"⚠️ API respondió {resp.status}: {text}")
        except Exception as e:
            print("❌ Error conectando a API:", e)


def extract_embed_text(embed: discord.Embed) -> str:
    """Extrae todo el texto posible de un embed."""
    parts = []
    if embed.title:
        parts.append(f"**{embed.title}**")
    if embed.description:
        parts.append(embed.description)
    if embed.fields:
        for f in embed.fields:
            parts.append(f"**{f.name}:** {f.value}")
    if embed.footer and embed.footer.text:
        parts.append(f"Footer: {embed.footer.text}")
    if embed.author and embed.author.name:
        parts.append(f"Autor: {embed.author.name}")
    return "\n".join(parts)


def parse_embed_content(message: discord.Message):
    """Extrae toda la información relevante del mensaje o embed."""
    players = []
    content_parts = []

    # Extraer texto de embeds
    if message.embeds:
        for emb in message.embeds:
            content_parts.append(extract_embed_text(emb))

    # Si además el mensaje tiene contenido (raro en webhooks, pero por si acaso)
    if message.content:
        content_parts.append(message.content)

    # Unir todo el texto
    joined = "\n".join(content_parts)
    print("🧩 Texto combinado del embed/mensaje:\n", joined)

    # Buscar licencias y detalles
    license_matches = list(RE_LICENSE_LINE.finditer(joined))
    details_matches = list(RE_PLAYER_DETAILS.finditer(joined))

    for idx, m in enumerate(license_matches):
        license_id = m.group("license_id")
        player_details = details_matches[idx].group("details").strip() if idx < len(details_matches) else "Desconocido"
        players.append({
            "license": license_id,
            "player_details": player_details
        })

    # Buscar hora o usar la hora del mensaje
    time_match = RE_TIME.search(joined)
    hora = time_match.group("hour") if time_match else message.created_at.replace(tzinfo=timezone.utc).isoformat()

    return joined, players, hora


# === EVENTOS DEL BOT ===

@client.event
async def on_ready():
    print(f"🤖 Bot listo: {client.user}")


@client.event
async def on_message(message: discord.Message):
    # Evitar que lea sus propios mensajes
    if message.author == client.user:
        return

    # Filtrar por canal y autor específico
    if message.channel.id != LOG_CHANNEL_ID:
        return

    # Si el mensaje viene de un webhook/bot en particular
    if message.author.bot and message.author.id == TARGET_BOT_ID:
        print(f"📨 Mensaje recibido del bot objetivo: {message.author}")

        joined_content, players, hora = parse_embed_content(message)

        if not joined_content:
            print("⚠️ El mensaje del bot está vacío o no contiene embeds.")
            return

        if not players:
            print("⚠️ No se encontraron 'license' en el mensaje del bot.")
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
