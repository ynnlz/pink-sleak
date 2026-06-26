import os
import asyncio
import threading

import discord
from discord.ext import commands
from discord.ui import View, Button
from flask import Flask
from dotenv import load_dotenv


# =========================
# CONFIG LOCAL
# =========================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN manquant dans les variables d'environnement.")


# =========================
# CONFIG BOT
# =========================

BOT_NAME = "Pink Leak's"
BOT_COLOR = 0xFF3EA8

TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "🎫・tickets")
SUPPORT_ROLE_NAME = os.getenv("SUPPORT_ROLE_NAME", "Staff")


# =========================
# SERVEUR WEB POUR RENDER
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Pink Leak's Bot est en ligne ✅"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )

threading.Thread(target=run_web_server, daemon=True).start()


# =========================
# INTENTS
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# =========================
# VIEWS / BOUTONS
# =========================

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Créer un ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="pinkleaks_create_ticket"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user

        if guild is None:
            await interaction.response.send_message(
                "❌ Cette action doit être utilisée dans un serveur.",
                ephemeral=True
            )
            return

        existing_ticket = discord.utils.get(
            guild.text_channels,
            topic=f"ticket_owner:{user.id}"
        )

        if existing_ticket:
            await interaction.response.send_message(
                f"❌ Tu as déjà un ticket ouvert : {existing_ticket.mention}",
                ephemeral=True
            )
            return

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)

        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        safe_name = user.name.lower().replace(" ", "-")[:18]
        channel_name = f"ticket-{safe_name}"

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"ticket_owner:{user.id}"
        )

        embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=(
                f"Bienvenue {user.mention}.\n\n"
                "Explique clairement ta demande, un membre du staff te répondra dès que possible.\n\n"
                "🔒 Pour fermer ce ticket, clique sur le bouton ci-dessous."
            ),
            color=BOT_COLOR
        )

        embed.set_footer(text=f"{BOT_NAME} • Support")

        await ticket_channel.send(
            content=f"{user.mention}",
            embed=embed,
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"✅ Ton ticket a été créé : {ticket_channel.mention}",
            ephemeral=True
        )


class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fermer le ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="pinkleaks_close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Impossible de fermer ce salon.",
                ephemeral=True
            )
            return

        is_ticket = channel.topic and channel.topic.startswith("ticket_owner:")

        if not is_ticket:
            await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket.",
                ephemeral=True
            )
            return

        owner_id = int(channel.topic.replace("ticket_owner:", ""))
        is_owner = interaction.user.id == owner_id
        is_staff = interaction.user.guild_permissions.manage_channels

        if not is_owner and not is_staff:
            await interaction.response.send_message(
                "❌ Tu n'as pas la permission de fermer ce ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Fermeture du ticket dans 5 secondes..."
        )

        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket fermé par {interaction.user}")


# =========================
# CLASSE BOT
# =========================

class PinkLeaksBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(CloseTicketView())


bot = PinkLeaksBot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="Pink Leak's 🎀"
    )

    await bot.change_presence(
        status=discord.Status.online,
        activity=activity
    )

    print("====================================")
    print(f"✅ Connecté : {bot.user}")
    print(f"🆔 ID : {bot.user.id}")
    print("🚀 Pink Leak's Bot lancé avec succès")
    print("====================================")


# =========================
# COMMANDES
# =========================

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)

    embed = discord.Embed(
        title="🏓 Pong",
        description=f"Latence : `{latency}ms`",
        color=BOT_COLOR
    )

    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📖 Commandes Pink Leak's",
        description="Voici la liste des commandes disponibles.",
        color=BOT_COLOR
    )

    embed.add_field(
        name="`!ping`",
        value="Vérifie si le bot est en ligne.",
        inline=False
    )

    embed.add_field(
        name="`!reglement`",
        value="Affiche le règlement du serveur.",
        inline=False
    )

    embed.add_field(
        name="`!setup_ticket`",
        value="Envoie le panel de création de ticket.",
        inline=False
    )

    embed.add_field(
        name="`!close`",
        value="Ferme le ticket actuel.",
        inline=False
    )

    embed.set_footer(text=f"{BOT_NAME} • Help")

    await ctx.send(embed=embed)


@bot.command()
async def reglement(ctx):
    embed = discord.Embed(
        title="📜 Règlement Pink Leak's",
        description="Merci de lire et respecter les règles du serveur.",
        color=BOT_COLOR
    )

    embed.add_field(
        name="1. Respect obligatoire",
        value="Aucune insulte, menace, discrimination ou harcèlement ne sera toléré.",
        inline=False
    )

    embed.add_field(
        name="2. Contenu interdit",
        value="Aucun contenu volé, privé, non autorisé ou diffusé sans consentement n'est accepté.",
        inline=False
    )

    embed.add_field(
        name="3. Sécurité",
        value="Ne partage jamais tes informations personnelles, mots de passe ou moyens de paiement.",
        inline=False
    )

    embed.add_field(
        name="4. Tickets",
        value="Ouvre un ticket uniquement pour une vraie demande. Les abus peuvent mener à une sanction.",
        inline=False
    )

    embed.add_field(
        name="5. Staff",
        value="Les décisions du staff doivent être respectées.",
        inline=False
    )

    embed.set_footer(text=f"{BOT_NAME} • Règlement")

    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup_ticket(ctx):
    embed = discord.Embed(
        title="🎫 Support Pink Leak's",
        description=(
            "Besoin d'aide ou d'information ?\n\n"
            "Clique sur le bouton ci-dessous pour ouvrir un ticket privé avec le staff."
        ),
        color=BOT_COLOR
    )

    embed.set_footer(text=f"{BOT_NAME} • Tickets")

    await ctx.send(embed=embed, view=TicketPanelView())


@bot.command()
async def close(ctx):
    channel = ctx.channel

    if not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ Cette commande doit être utilisée dans un salon texte.")
        return

    is_ticket = channel.topic and channel.topic.startswith("ticket_owner:")

    if not is_ticket:
        await ctx.send("❌ Ce salon n'est pas un ticket.")
        return

    owner_id = int(channel.topic.replace("ticket_owner:", ""))
    is_owner = ctx.author.id == owner_id
    is_staff = ctx.author.guild_permissions.manage_channels

    if not is_owner and not is_staff:
        await ctx.send("❌ Tu n'as pas la permission de fermer ce ticket.")
        return

    await ctx.send("🔒 Fermeture du ticket dans 5 secondes...")
    await asyncio.sleep(5)
    await channel.delete(reason=f"Ticket fermé par {ctx.author}")


# =========================
# GESTION ERREURS
# =========================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")

    elif isinstance(error, commands.CommandNotFound):
        return

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Il manque un argument dans ta commande.")

    else:
        await ctx.send(f"❌ Erreur : `{error}`")
        raise error


# =========================
# START BOT
# =========================

bot.run(TOKEN)
