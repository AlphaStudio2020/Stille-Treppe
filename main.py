from discord.ext import commands
import discord
import asyncio

bot = commands.Bot(command_prefix="!")
active_mutes = {}  # Speichert aktive "Stille Treppe"-Sanktionen

AUTHORIZED_ROLE_ID = Role_ID  # Ersetze mit der ID der autorisierten Rolle
LOG_CHANNEL_ID = LOG_ID  # Ersetze mit der ID des Log-Kanals

@bot.command(name='st')
async def mute(ctx, member: discord.Member, duration: int):
    global active_mutes

    # Überprüfen, ob der Benutzer die richtige Rolle hat
    if not any(role.id == AUTHORIZED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("Du hast keine Berechtigung, diesen Befehl zu verwenden.")
        return

    # Überprüfen, ob das Ziel in einem Sprachkanal ist
    if member.voice is None or member.voice.channel is None:
        await ctx.send(f'{member.mention} ist nicht in einem Sprachkanal.')
        return

    # Falls der Benutzer bereits auf der Stille Treppe ist
    if member.id in active_mutes:
        await ctx.send(f'{member.mention} ist bereits auf der Stille Treppe.')
        return

    # Erstelle einen neuen privaten Sprachkanal
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(connect=False),
        member: discord.PermissionOverwrite(connect=True)
    }
    silent_channel = await ctx.guild.create_voice_channel(
        name=f"Stille Treppe für {member.display_name}",
        overwrites=overwrites,
        reason="Stille Treppe"
    )

    # Merke dir den aktuellen Kanal des Benutzers
    original_channel = member.voice.channel

    # Verschiebe den Benutzer in den neuen Sprachkanal
    await member.move_to(silent_channel)
    await ctx.send(f'{member.mention} wurde auf die Stille Treppe gesetzt.')

    # Log-Kanal abrufen
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel is None:
        await ctx.send(f"Der Log-Kanal mit der ID {LOG_CHANNEL_ID} wurde nicht gefunden.")
        return

    # Task: Überwache den Benutzer und verschiebe ihn zurück, wenn er den Kanal verlässt
    async def monitor_user():
        while True:
            if member.voice and member.voice.channel != silent_channel:
                await member.move_to(silent_channel)
                await log_channel.send(f"{member.mention} hat versucht, den Kanal zu wechseln und wurde zurück auf die Stille Treppe verschoben.")
            await asyncio.sleep(1)

    # Starte die Überwachung des Benutzers in einer Hintergrundaufgabe
    monitor_task = bot.loop.create_task(monitor_user())
    active_mutes[member.id] = {
        "silent_channel": silent_channel,
        "original_channel": original_channel,
        "task": monitor_task
    }

    try:
        await asyncio.sleep(duration)
    finally:
        await unmute(ctx, member, forced=False)

@bot.command(name='st_remove')
async def unmute(ctx, member: discord.Member, forced: bool = True):
    global active_mutes

    # Überprüfen, ob der Benutzer die richtige Rolle hat
    if forced and not any(role.id == AUTHORIZED_ROLE_ID for role in ctx.author.roles):
        await ctx.send("Du hast keine Berechtigung, diesen Befehl zu verwenden.")
        return

    # Falls der Benutzer nicht auf der Stille Treppe ist
    if member.id not in active_mutes:
        await ctx.send(f'{member.mention} ist nicht auf der Stille Treppe.')
        return

    # Details der Stille Treppe abrufen
    mute_data = active_mutes.pop(member.id)
    silent_channel = mute_data["silent_channel"]
    original_channel = mute_data["original_channel"]
    monitor_task = mute_data["task"]

    # Überwachung beenden
    monitor_task.cancel()

    # Benutzer in den ursprünglichen Kanal verschieben, falls er noch im stummen Kanal ist
    if member.voice and member.voice.channel == silent_channel:
        await member.move_to(original_channel)
        await ctx.send(f'{member.mention} wurde von der Stille Treppe genommen.')

    # Log-Eintrag
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f'{member.mention} wurde von der Stille Treppe entfernt.')

    # Temporären Sprachkanal löschen
    await silent_channel.delete()

bot.run('BOT_TOKEN')
