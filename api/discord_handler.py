"""
Module pour gérer les interactions avec Discord.
Gère la création de salons et récupération des IDs.
"""

import discord
from discord.ext import commands
import asyncio
from . import utils


class DiscordHandler:
    """Classe pour gérer les opérations Discord."""
    
    def __init__(self):
        self.bot = None
        self.is_ready = False
        self.loop = None
        self.guild_id = None
        
    async def initialize(self):
        """Initialise la connexion au bot Discord."""
        if self.is_ready:
            return
            
        try:
            token = utils.CONFIG.get('discord', {}).get('token')
            self.guild_id = utils.CONFIG.get('discord', {}).get('guild_id')
            
            if not token:
                raise ValueError("Discord token non configuré dans config.json")
            if not self.guild_id:
                raise ValueError("Discord guild_id non configuré dans config.json")
            
            intents = discord.Intents.default()
            intents.message_content = True
            self.bot = commands.Bot(command_prefix="!", intents=intents)
            
            @self.bot.event
            async def on_ready():
                print(f"Discord bot connecté en tant que {self.bot.user}")
                self.is_ready = True
            
            # Démarrer le bot dans un thread séparé
            await self.bot.start(token)
            
        except Exception as e:
            print(f"Erreur lors de l'initialisation du bot Discord: {e}")
            raise
    
    async def create_channel(self, channel_name: str, category_id: int = None) -> str:
        """
        Crée un nouveau salon Discord et retourne son ID.
        
        Args:
            channel_name: Le nom du salon à créer
            category_id: L'ID de la catégorie (optionnel)
        
        Returns:
            str: L'ID du salon créé
        """
        if not self.is_ready:
            await self.initialize()
        
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                raise ValueError(f"Serveur Discord avec l'ID {self.guild_id} non trouvé")
            
            print(f"Création du salon '{channel_name}' sur le serveur '{guild.name}'")
            # Créer le salon
            if category_id:
                category = guild.get_channel(category_id)
                print(f"Création du salon '{channel_name}' dans la catégorie '{category.name}' sur le serveur '{guild.name}'")
                channel = await guild.create_text_channel(channel_name, category=category)
            else:
                print(f"Création du salon '{channel_name}' sans catégorie sur le serveur '{guild.name}'")
                channel = await guild.create_text_channel(channel_name)
            
            return str(channel.id)
        
        except Exception as e:
            print(f"Erreur lors de la création du salon Discord: {e}")
            raise
    
    async def delete_channel(self, channel_id: int) -> bool:
        """
        Supprime un salon Discord.
        
        Args:
            channel_id: L'ID du salon à supprimer
        
        Returns:
            bool: True si la suppression a réussi, False sinon
        """
        if not self.is_ready:
            await self.initialize()
        
        try:
            guild = self.bot.get_guild(self.guild_id)
            channel = guild.get_channel(int(channel_id))
            
            if channel:
                await channel.delete()
                return True
            return False
        
        except Exception as e:
            print(f"Erreur lors de la suppression du salon Discord: {e}")
            return False


# Instance globale du gestionnaire Discord
_discord_handler = None


def get_discord_handler():
    """Retourne l'instance globale du gestionnaire Discord."""
    global _discord_handler
    if _discord_handler is None:
        _discord_handler = DiscordHandler()
    return _discord_handler


async def create_channel(title: str, category_id: int = None) -> str:
    """
    Crée un salon Discord en une seule opération rapide.
    Utilisé pour l'API FastAPI (mode synchrone).
    
    Args:
        title: Le titre du journal
        category_id: L'ID de la catégorie (optionnel)
    Returns:
        str: L'ID du salon créé
    """
    token = utils.CONFIG.get('discord', {}).get('token')
    guild_id = utils.CONFIG.get('discord', {}).get('guild_id')
    
    if not token or not guild_id:
        raise ValueError("Configuration Discord incomplète")
    
    # Nettoyer le nom du salon
    channel_name = title.lower().replace(" ", "-")[:32]
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    channel_id = None
    bot_ready = asyncio.Event()
    
    @bot.event
    async def on_ready():
        nonlocal channel_id
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                raise ValueError(f"Serveur Discord avec l'ID {guild_id} non trouvé")
            
            if category_id:
                category = guild.get_channel(category_id)
                print(f"Création du salon '{channel_name}' dans la catégorie '{category.name}' sur le serveur '{guild.name}'")
                channel = await guild.create_text_channel(channel_name, category=category)
            else:
                print(f"Création du salon '{channel_name}' sans catégorie sur le serveur '{guild.name}'")
                channel = await guild.create_text_channel(channel_name)
            
            channel_id = str(channel.id)
        except Exception as e:
            print(f"Erreur: {e}")
        finally:
            bot_ready.set()
            await bot.close()
    
    try:
        # Lancer le bot et attendre qu'il soit prêt
        bot_task = asyncio.create_task(bot.start(token))
        
        # Attendre avec timeout
        try:
            await asyncio.wait_for(bot_ready.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            await bot.close()
            raise ValueError("Timeout: bot Discord n'a pas pu se connecter")
        
        # Attendre que le bot se ferme proprement
        try:
            await asyncio.wait_for(bot_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
            
    except Exception as e:
        raise ValueError(f"Erreur création salon Discord: {e}")
    finally:
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
    
    if not channel_id:
        raise ValueError("Impossible de créer le salon Discord")
    
    return channel_id


async def delete_channel(channel_id: str) -> bool:
    """
    Supprime un salon Discord en une seule opération rapide.
    Utilisé pour l'API FastAPI (mode synchrone).
    
    Args:
        channel_id: L'ID du salon à supprimer
    
    Returns:
        bool: True si la suppression a réussi, False sinon
    """
    token = utils.CONFIG.get('discord', {}).get('token')
    guild_id = utils.CONFIG.get('discord', {}).get('guild_id')
    
    if not token or not guild_id:
        raise ValueError("Configuration Discord incomplète")
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    success = False
    bot_ready = asyncio.Event()
    
    @bot.event
    async def on_ready():
        nonlocal success
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                raise ValueError(f"Serveur Discord avec l'ID {guild_id} non trouvé")
            
            channel = guild.get_channel(int(channel_id))
            if channel:
                await channel.delete()
                success = True
            else:
                print(f"Avertissement: Salon Discord {channel_id} non trouvé")
                success = False
        except Exception as e:
            print(f"Erreur: {e}")
            success = False
        finally:
            bot_ready.set()
            await bot.close()
    
    try:
        # Lancer le bot et attendre qu'il soit prêt
        bot_task = asyncio.create_task(bot.start(token))
        
        # Attendre avec timeout
        try:
            await asyncio.wait_for(bot_ready.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            await bot.close()
            raise ValueError("Timeout: bot Discord n'a pas pu se connecter")
        
        # Attendre que le bot se ferme proprement
        try:
            await asyncio.wait_for(bot_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
            
    except Exception as e:
        print(f"Erreur suppression salon Discord: {e}")
        success = False
    finally:
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
    
    return success


async def get_channel_messages(channel_id: str, limit: int = 100) -> list:
    """
    Récupère les messages d'un salon Discord.
    
    Args:
        channel_id: L'ID du salon Discord
        limit: Le nombre maximum de messages à récupérer (par défaut 100)
    
    Returns:
        list: Liste des messages avec their metadata
    """
    token = utils.CONFIG.get('discord', {}).get('token')
    guild_id = utils.CONFIG.get('discord', {}).get('guild_id')
    
    if not token or not guild_id:
        raise ValueError("Configuration Discord incomplète")
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    messages = []
    bot_ready = asyncio.Event()
    
    @bot.event
    async def on_ready():
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                raise ValueError(f"Serveur Discord avec l'ID {guild_id} non trouvé")
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                print(f"Avertissement: Salon Discord {channel_id} non trouvé")
                bot_ready.set()
                await bot.close()
                return
            
            # Récupérer les messages
            async for message in channel.history(limit=limit):
                msg_data = {
                    "id": str(message.id),
                    "author": {
                        "name": message.author.name,
                        "id": str(message.author.id),
                        "is_bot": message.author.bot
                    },
                    "content": message.content,
                    "timestamp": message.created_at.isoformat(),
                    "edited_at": message.edited_at.isoformat() if message.edited_at else None,
                    "attachments": [
                        {
                            "url": att.url,
                            "filename": att.filename,
                            "size": att.size
                        }
                        for att in message.attachments
                    ],
                    "embeds": len(message.embeds),
                    "reactions": {
                        str(reaction.emoji): reaction.count
                        for reaction in message.reactions
                    }
                }
                messages.append(msg_data)
        except Exception as e:
            print(f"Erreur lors de la récupération des messages: {e}")
        finally:
            bot_ready.set()
            await bot.close()
    
    try:
        # Lancer le bot et attendre qu'il soit prêt
        bot_task = asyncio.create_task(bot.start(token))
        
        # Attendre avec timeout
        try:
            await asyncio.wait_for(bot_ready.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            await bot.close()
            raise ValueError("Timeout: bot Discord n'a pas pu se connecter")
        
        # Attendre que le bot se ferme proprement
        try:
            await asyncio.wait_for(bot_task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
            
    except Exception as e:
        print(f"Erreur récupération messages Discord: {e}")
    finally:
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
    
    return messages
