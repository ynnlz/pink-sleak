import asyncio
import json
import os
from pathlib import Path

import discord
from aiohttp import web
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("La variable DISCORD_TOKEN est obligatoire.")

BASE_DIR = Path(__file__).resolve().parent
EMBEDS_FILE = BASE_DIR / "embeds.json"


def load_embeds():
    with EMBEDS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def make_embed(embed_name, **values):
    embeds = load_embeds()
    data = embeds[embed_name]

    title = data.get("title", "").format(**values)
    description = data.get("description", "").format(**values)
    color = int(data.get("color", "0xFF69B4"), 16)

    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )

    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"].format(**values))

    if data.get("image"):
        embed.set_image(url=data["image"].format(**values))

    footer = data.get("footer")
    if footer:
        embed.set_footer(text=footer.format(**values))

    for field in data.get("fields", []):
        embed.add_field(
            name=field.get("name", "").format(**values),
            value=field.get("value", "").format(**values),
            inline=field.get("inline", False)
        )

    return embed


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Connecte en tant que {bot.user}")


@bot.command()
async def ping(ctx):
    embed = make_embed("ping", user=ctx.author.mention)
    await ctx.send(embed=embed)


@bot.command(name="helpme")
async def helpme(ctx):
    embed = make_embed("help", user=ctx.author.mention)
    await ctx.send(embed=embed)


@bot.command()
async def avatar(ctx, member: discord.Member | None = None):
    member = member or ctx.author
    embed = make_embed(
        "avatar",
        user=member.mention,
        username=member.display_name,
        avatar_url=member.display_avatar.url
    )
    await ctx.send(embed=embed)


async def home(_request):
    return web.Response(text="Pink Sleak est en ligne.")


async def health(_request):
    return web.json_response({
        "ok": True,
        "bot": "connected" if bot.is_ready() else "starting"
    })


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Serveur web lance sur le port {PORT}")


async def main():
    await start_web_server()
    await bot.start(TOKEN)


asyncio.run(main())
