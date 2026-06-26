import asyncio
import json
import os
import re
from pathlib import Path

import discord
from aiohttp import web
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PORT = int(os.getenv("PORT", "10000"))
STAFF_ROLE_ID = os.getenv("STAFF_ROLE_ID")
TICKET_CATEGORY_ID = os.getenv("TICKET_CATEGORY_ID")

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

    safe_values = {key: str(value) for key, value in values.items()}
    title = data.get("title", "").format(**safe_values)
    description = data.get("description", "").format(**safe_values)
    color = int(data.get("color", "0xFF69B4"), 16)

    embed = discord.Embed(title=title, description=description, color=color)

    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"].format(**safe_values))

    if data.get("image"):
        embed.set_image(url=data["image"].format(**safe_values))

    footer = data.get("footer")
    if footer:
        embed.set_footer(text=footer.format(**safe_values))

    for field in data.get("fields", []):
        embed.add_field(
            name=field.get("name", "").format(**safe_values),
            value=field.get("value", "").format(**safe_values),
            inline=field.get("inline", False)
        )

    return embed


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = value.strip("-")
    return value or "membre"


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reclamation / signalement",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_report"
    )
    async def report_ticket(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        await create_ticket(interaction, "report")

    @discord.ui.button(
        label="Commander VIP",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_vip"
    )
    async def vip_ticket(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        await create_ticket(interaction, "vip")


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fermer le ticket",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close"
    )
    async def close_ticket(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Cette action doit etre utilisee dans un ticket.", ephemeral=True
            )
            return

        if not channel.name.startswith(("ticket-", "vip-")):
            await interaction.response.send_message(
                "Ce salon ne ressemble pas a un ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=make_embed("ticket_closing", user=interaction.user.mention)
        )
        await asyncio.sleep(3)
        await channel.delete(reason=f"Ticket ferme par {interaction.user}")


def find_existing_ticket(guild, member, ticket_type):
    prefix = "vip" if ticket_type == "vip" else "ticket"
    marker = str(member.id)
    for channel in guild.text_channels:
        if channel.name.startswith(f"{prefix}-") and marker in channel.topic:
            return channel
    return None


async def create_ticket(interaction, ticket_type):
    guild = interaction.guild
    member = interaction.user

    if guild is None:
        await interaction.response.send_message(
            "Les tickets doivent etre crees depuis un serveur.", ephemeral=True
        )
        return

    existing = find_existing_ticket(guild, member, ticket_type)
    if existing:
        await interaction.response.send_message(
            embed=make_embed("ticket_already_open", channel=existing.mention),
            ephemeral=True
        )
        return

    category = None
    if TICKET_CATEGORY_ID:
        category = guild.get_channel(int(TICKET_CATEGORY_ID))

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True,
            read_message_history=True
        )
    }

    if STAFF_ROLE_ID:
        staff_role = guild.get_role(int(STAFF_ROLE_ID))
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

    prefix = "vip" if ticket_type == "vip" else "ticket"
    channel_name = f"{prefix}-{slugify(member.name)}"[:90]
    topic = f"{ticket_type} ticket - owner:{member.id}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category if isinstance(category, discord.CategoryChannel) else None,
        overwrites=overwrites,
        topic=topic,
        reason=f"Ticket {ticket_type} cree par {member}"
    )

    embed_name = "ticket_report_created" if ticket_type == "report" else "ticket_vip_created"
    await channel.send(
        content=member.mention,
        embed=make_embed(embed_name, user=member.mention),
        view=CloseTicketView()
    )

    await interaction.response.send_message(
        embed=make_embed("ticket_created_private", channel=channel.mention),
        ephemeral=True
    )


@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
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


@bot.command(name="tickets")
@commands.has_permissions(administrator=True)
async def tickets(ctx):
    await ctx.send(embed=make_embed("ticket_panel"), view=TicketView())


@tickets.error
async def tickets_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("Tu dois etre administrateur pour installer le panneau de tickets.")


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
